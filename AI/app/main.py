import os
import time
import uuid
import base64
import shutil
from pathlib import Path
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.encoders import jsonable_encoder
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.db.vector_store import MongoDBAtlasVectorSearch, get_embedding_model
from app.core.fast_path import FastPathRouter
from app.core.debouncer import DebounceManager
from app.core.anonymizer import mask_pii
from app.core.telemetry import telemetry_emitter
from app.core.orchestrator import MasterOrchestrator
from app.templates.flex_messages import parse_postback_action


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Startup:
    Executes complete system pre-computation and warm-up before serving any traffic:
    1. Pre-loads and warms up intfloat/multilingual-e5-small (eliminates cold-start & download progress bars).
    2. Builds in-memory FAISS IndexFlatIP and BM25Okapi catalog from Atlas.
    3. Wakes up Ollama satellite worker LLM (qwen3:1.7b) into memory.
    4. Pings MongoDB Atlas connection.
    """
    print("\n🚀 [System Warm-up] Initiating pre-computation & model warm-up (eliminating cold-start latency)...", flush=True)

    # 1. Embedding Model Warm-up
    t0 = time.perf_counter()
    try:
        model = get_embedding_model()
        _ = model.encode("query: warm up", normalize_embeddings=True)
        t_emb = (time.perf_counter() - t0) * 1000
        print(f"   ✅ [1/4] Embedding Model: 'intfloat/multilingual-e5-small' ready (warm-up {t_emb:.1f} ms)", flush=True)
    except Exception as e:
        print(f"   ❌ [1/4] Embedding Model Warm-up Error: {e}", flush=True)

    # 2. In-Memory Hybrid Store Warm-up (FAISS + BM25)
    t0 = time.perf_counter()
    try:
        vector_store = MongoDBAtlasVectorSearch()
        count = await vector_store.warm_up_catalog()
        t_store = (time.perf_counter() - t0) * 1000
        print(f"   ✅ [2/4] In-Memory Hybrid Store: Loaded {count} products into FAISS (IndexFlatIP) + BM25Okapi successfully ({t_store:.1f} ms)", flush=True)
    except Exception as e:
        print(f"   ❌ [2/4] In-Memory Hybrid Store Warm-up Error: {e}", flush=True)

    # 3. Local LLM Worker & Brain Warm-up (Ollama)
    models_to_warm = [
        ("Worker", settings.OLLAMA_WORKER_MODEL),
        ("Main Brain", settings.OLLAMA_MAIN_MODEL)
    ]
    async with httpx.AsyncClient(timeout=90.0) as client:
        for role, m_name in models_to_warm:
            t0 = time.perf_counter()
            try:
                res = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/chat/completions",
                    json={
                        "model": m_name,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1
                    }
                )
                t_ollama = (time.perf_counter() - t0) * 1000
                if res.status_code == 200:
                    print(f"   ✅ [3/4] Ollama {role}: Loaded model '{m_name}' into memory ({t_ollama:.1f} ms)", flush=True)
                else:
                    print(f"   ⚠️ [3/4] Ollama {role}: Returned status {res.status_code} ({t_ollama:.1f} ms)", flush=True)
            except Exception as e:
                print(f"   ⚠️ [3/4] Ollama {role}: Could not warm up '{m_name}' ({e})", flush=True)

    # 4. Database Connection Ping (MongoDB Atlas)
    t0 = time.perf_counter()
    try:
        mongo_client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
        await mongo_client.admin.command("ping")
        t_db = (time.perf_counter() - t0) * 1000
        print(f"   ✅ [4/4] Database Connection: Ping MongoDB Atlas database '{settings.MONGO_DB_NAME}' succeeded ({t_db:.1f} ms)", flush=True)
    except Exception as e:
        print(f"   ❌ [4/4] Database Connection Error: {e}", flush=True)

    print(f"🎉 [System Ready] {settings.APP_NAME} is ready to serve traffic! (Mode: {settings.RETRIEVAL_MODE})\n", flush=True)

    yield

    print("🛑 [System Shutdown] Shutting down application gracefully...", flush=True)


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan
)

# Initialize core routers and orchestrator (100% Real Production Execution)
fast_path_router = FastPathRouter()
orchestrator = MasterOrchestrator(mock_mode=False)

async def handle_debounced_batch(user_id: str, items: list):
    """Callback triggered when the debounce buffer window closes."""
    for item in items:
        if item.get("type") == "text" and "content" in item:
            item["content"] = mask_pii(item["content"])
    await orchestrator.process_session(user_id, items)

debouncer = DebounceManager(
    wait_seconds=settings.DEBOUNCE_WAIT_SECONDS,
    on_flush_callback=handle_debounced_batch
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "retrieval_mode": settings.RETRIEVAL_MODE,
        "is_warmed_up": MongoDBAtlasVectorSearch.is_warmed_up(),
        "catalog_size": len(MongoDBAtlasVectorSearch._catalog),
        "debounce_wait_seconds": settings.DEBOUNCE_WAIT_SECONDS
    }


@app.post("/api/v1/ingress")
async def ingress(request: Request):
    """
    Ingress Gateway:
    - Evaluates Fast-Path (Sub-2ms deterministic bypass or satellite worker classifier).
    - If bypassed: returns 200 immediately without hitting LLM or buffer.
    - Otherwise: buffers message into per-user DebounceManager and returns 202 Accepted.
    """
    payload = await request.json()
    user_id = payload.get("user_id", "default_user")
    content = payload.get("content", "")

    # Fast-Path Check via Two-Tier Router
    is_fast, fast_path_res = await fast_path_router.evaluate_fast_path(content)
    if is_fast:
        return JSONResponse(status_code=200, content=fast_path_res)

    # If base64 image payload was sent via JSON, persist to uploads/ as a real file on disk
    if payload.get("image_base64"):
        uploads_dir = os.path.abspath("uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        img_b64 = payload["image_base64"]
        clean_b64 = img_b64.split(",", 1)[1] if "," in img_b64 else img_b64
        fname = payload.get("file_name", "upload.png")
        safe_fname = f"{user_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}_{os.path.basename(fname)}"
        saved_img_path = os.path.join(uploads_dir, safe_fname)
        try:
            with open(saved_img_path, "wb") as f_img:
                f_img.write(base64.b64decode(clean_b64))
            payload["file_path"] = saved_img_path
            payload.pop("image_base64", None)
        except Exception as e:
            print(f"Error saving ingress base64: {e}")

    # Enqueue to Debounce Buffer
    await debouncer.add_event(user_id, payload)
    return JSONResponse(
        status_code=202,
        content={"status": "buffered", "wait_seconds": settings.DEBOUNCE_WAIT_SECONDS}
    )


@app.post("/api/v1/upload")
async def upload_document(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    caption: str = Form("")
):
    """
    Receives financial document image (PNG/JPG/PDF) via multipart/form-data.
    Saves file to uploads/ directory and enqueues event with real absolute file_path into Debouncer.
    """
    uploads_dir = os.path.abspath("uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    safe_filename = f"{user_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}_{os.path.basename(file.filename)}"
    saved_path = os.path.join(uploads_dir, safe_filename)

    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    image_event = {
        "user_id": user_id,
        "type": "image",
        "file_name": file.filename,
        "file_path": saved_path
    }
    await debouncer.add_event(user_id, image_event)

    if caption and caption.strip():
        text_event = {
            "user_id": user_id,
            "type": "text",
            "content": mask_pii(caption.strip())
        }
        await debouncer.add_event(user_id, text_event)

    return JSONResponse(
        status_code=202,
        content={
            "status": "buffered",
            "saved_file": safe_filename,
            "file_path": saved_path,
            "wait_seconds": settings.DEBOUNCE_WAIT_SECONDS
        }
    )


@app.post("/api/v1/postback")
async def postback(request: Request):
    """
    LINE Postback Action Webhook:
    Parses postback query parameters (e.g. action=edit_receipt&receipt_id=rcpt_100)
    for interactive human-in-the-loop workflows.
    """
    payload = await request.json()
    data_str = payload.get("data", "")
    parsed = parse_postback_action(data_str)
    return JSONResponse(status_code=200, content=parsed)


@app.get("/api/v1/telemetry/stream")
async def telemetry_stream(session_id: str):
    """
    Real-time Server-Sent Events (SSE) telemetry stream.
    Clients (Dashboard / Web Demo) subscribe to stream live agent wire activations,
    thought logs, and cashflow metrics.
    """
    return StreamingResponse(
        telemetry_emitter.subscribe_events(session_id),
        media_type="text/event-stream"
    )


@app.get("/", response_class=HTMLResponse)
@app.get("/chat", response_class=HTMLResponse)
async def serve_demo_ui():
    """Serves the interactive live chat and telemetry monitor web UI."""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "demo_ui.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h2>Demo UI template not found</h2>", status_code=404)


@app.post("/api/v1/chat")
async def chat_direct(request: Request):
    """
    Direct Interactive Chat Endpoint (Zero Debounce Wait):
    - Evaluates Fast-Path first (< 2ms bypass).
    - Processes uploaded image (base64) or financial text immediately through MasterOrchestrator.
    - Returns complete synthesized response, cashflow metrics, and loan recommendations.
    """
    payload = await request.json()
    user_id = payload.get("user_id", "default_user")
    content = payload.get("content", "")
    image_base64 = payload.get("image_base64")
    file_name = payload.get("file_name", "uploaded_image.png")

    # 1. Fast-Path Check
    if content:
        is_fast, fast_path_res = await fast_path_router.evaluate_fast_path(content)
        if is_fast:
            return JSONResponse(status_code=200, content=fast_path_res)

    # 2. Build inputs
    inputs = []
    if content:
        masked_text = mask_pii(content)
        inputs.append({"type": "text", "content": masked_text})

    # Handle image base64 decode if present
    if image_base64:
        uploads_dir = os.path.join(os.getcwd(), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        clean_base64 = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
        safe_name = f"{uuid.uuid4().hex[:8]}_{os.path.basename(file_name)}"
        saved_img_path = os.path.join(uploads_dir, safe_name)
        try:
            with open(saved_img_path, "wb") as f_img:
                f_img.write(base64.b64decode(clean_base64))
            inputs.append({"type": "image", "file_path": saved_img_path, "file_name": safe_name})
        except Exception as e:
            print(f"Error saving image base64: {e}")

    if not inputs:
        inputs.append({"type": "text", "content": "ขอตรวจสอบสภาพคล่องทางการเงิน"})

    # 3. Process via MasterOrchestrator
    result = await orchestrator.process_session(user_id, inputs)
    return JSONResponse(status_code=200, content=jsonable_encoder(result))


@app.get("/api/v1/profile")
async def get_user_profile(user_id: str = "sme_user_001"):
    """Fetches real SME business financial profile from MongoDB Atlas."""
    profile = await orchestrator.get_user_financial_profile(user_id)
    return JSONResponse(status_code=200, content=jsonable_encoder(profile))

