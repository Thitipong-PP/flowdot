import os
import time
import uuid
import base64
import logging
import json
import hmac
import re
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
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
from app.schemas.chat import AssistantChatRequest
from app.core.request_context import current_request_id
from app.schemas.events import ActiveNode, NodeStatus, TelemetryEvent


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

# Request audit logs intentionally exclude request/response bodies, headers, query
# values, user IDs, and file names because they may contain PII or secrets.
_audit_logger = logging.getLogger("flowdot.audit")
_audit_logger.setLevel(logging.INFO)
if not _audit_logger.handlers:
    _audit_logger.addHandler(logging.StreamHandler())
    _audit_dir = Path(__file__).resolve().parents[1] / ".data" / "logs"
    _audit_dir.mkdir(parents=True, exist_ok=True)
    _audit_logger.addHandler(RotatingFileHandler(_audit_dir / "http-audit.jsonl", maxBytes=10_000_000, backupCount=7, encoding="utf-8"))


@app.middleware("http")
async def request_audit_and_access_control(request: Request, call_next):
    started = time.perf_counter()
    supplied_request_id = request.headers.get("x-request-id", "")
    request_id = supplied_request_id if len(supplied_request_id) <= 64 and re.fullmatch(r"[A-Za-z0-9._-]+", supplied_request_id) else uuid.uuid4().hex
    request.state.request_id = request_id
    status_code = 500
    path = request.url.path
    protected = path.startswith("/api/v1/")
    if protected:
        supplied = request.headers.get("authorization", "")
        token = settings.AI_SERVICE_TOKEN
        peer = request.client.host if request.client else ""
        is_loopback = peer in {"127.0.0.1", "::1", "localhost", "testclient"}
        if token:
            if len(token) < 32 or not supplied.startswith("Bearer ") or not hmac.compare_digest(supplied[7:], token):
                status_code = 401
                response = JSONResponse(status_code=status_code, content={"detail": "Unauthorized", "request_id": request_id})
                response.headers["X-Request-ID"] = request_id
                _log_http(request, status_code, started, request_id)
                return response
        elif not settings.DEBUG or not is_loopback:
            status_code = 503 if not settings.DEBUG else 401
            response = JSONResponse(status_code=status_code, content={"detail": "AI service authentication is not configured", "request_id": request_id})
            response.headers["X-Request-ID"] = request_id
            _log_http(request, status_code, started, request_id)
            return response
        content_length = request.headers.get("content-length")
        if content_length and (not content_length.isdigit() or len(content_length) > 12 or int(content_length) > (settings.MAX_UPLOAD_BYTES * 2 + 1_048_576)):
            status_code = 413
            response = JSONResponse(status_code=status_code, content={"detail": "Request exceeds size limit", "request_id": request_id})
            response.headers["X-Request-ID"] = request_id
            _log_http(request, status_code, started, request_id)
            return response
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        _audit_logger.error(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "request_id": request_id, "event": "http_request_failed", "path": path}))
        raise
    finally:
        _log_http(request, status_code, started, request_id)


def _log_http(request: Request, status_code: int, started: float, request_id: str) -> None:
    _audit_logger.info(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "event": "http_request_completed",
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
    }, separators=(",", ":")))


def _is_supported_upload(data: bytes) -> bool:
    return (
        data.startswith(b"\x89PNG\r\n\x1a\n")
        or data.startswith(b"\xff\xd8\xff")
        or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")
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
    content = mask_pii(str(payload.get("content", "")))
    payload["content"] = content

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
        try:
            decoded = base64.b64decode(clean_b64, validate=True)
        except (ValueError, base64.binascii.Error):
            return JSONResponse(status_code=400, content={"detail": "Invalid image upload"})
        if len(decoded) > settings.MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=413, content={"detail": "Upload exceeds size limit"})
        if not _is_supported_upload(decoded):
            return JSONResponse(status_code=415, content={"detail": "Unsupported image format"})
        safe_fname = f"{uuid.uuid4().hex}.upload"
        saved_img_path = os.path.join(uploads_dir, safe_fname)
        try:
            with open(saved_img_path, "wb") as f_img:
                f_img.write(decoded)
            payload["file_path"] = saved_img_path
            payload.pop("image_base64", None)
        except Exception:
            return JSONResponse(status_code=400, content={"detail": "Invalid image upload"})

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
    Receives a PNG/JPEG/WebP financial document image via multipart/form-data.
    Saves it under a generated name and enqueues it for the debounced pipeline.
    """
    uploads_dir = os.path.abspath("uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        return JSONResponse(status_code=415, content={"detail": "Unsupported file type"})
    safe_filename = f"{uuid.uuid4().hex}.upload"
    saved_path = os.path.join(uploads_dir, safe_filename)

    size = 0
    with open(saved_path, "wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.MAX_UPLOAD_BYTES:
                os.remove(saved_path)
                return JSONResponse(status_code=413, content={"detail": "Upload exceeds size limit"})
            buffer.write(chunk)
    with open(saved_path, "rb") as uploaded:
        if not _is_supported_upload(uploaded.read(12)):
            os.remove(saved_path)
            return JSONResponse(status_code=415, content={"detail": "Unsupported image format"})

    image_event = {
        "user_id": user_id,
        "type": "image",
        "file_name": safe_filename,
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
async def chat_direct(payload: AssistantChatRequest, request: Request):
    """
    Direct Interactive Chat Endpoint (Zero Debounce Wait):
    - Evaluates Fast-Path first (< 2ms bypass).
    - Processes financial text immediately through MasterOrchestrator.
    - Returns complete synthesized response, cashflow metrics, and loan recommendations.
    """
    user_id = payload.user_id
    content = mask_pii(payload.content)
    context_token = current_request_id.set(request.state.request_id)
    try:
        return await _process_direct_chat(payload, request, user_id, content)
    finally:
        current_request_id.reset(context_token)


async def _process_direct_chat(payload: AssistantChatRequest, request: Request, user_id: str, content: str):

    if payload.profile_context is None:
        await telemetry_emitter.emit(TelemetryEvent(
            session_id=user_id,
            event="CHAT_REJECTED_NO_PROFILE_CONTEXT",
            active_node=ActiveNode.INGRESS,
            node_status=NodeStatus.WARNING,
            thought_log="AI processing was not started because consented profile context is missing.",
        ))
        return JSONResponse(status_code=403, content={"detail": "Consented customer profile context is required."})

    # 1. Fast-Path Check
    if content:
        is_fast, fast_path_res = await fast_path_router.evaluate_fast_path(content)
        if is_fast:
            route_title = str(fast_path_res.get("title") or "")
            route_url = fast_path_res.get("login_url") or fast_path_res.get("settings_url") or fast_path_res.get("help_url")
            reply_text = f"{route_title}\n{route_url}" if route_url else route_title
            if fast_path_res.get("phone") or fast_path_res.get("line_oa"):
                reply_text += f"\nโทร {fast_path_res.get('phone', '—')} · LINE {fast_path_res.get('line_oa', '—')}"
            if not reply_text:
                reply_text = "เปิดเมนูที่เลือกให้แล้วค่ะ"
            await telemetry_emitter.emit(TelemetryEvent(
                session_id=user_id,
                event="FAST_PATH_COMPLETED",
                active_node=ActiveNode.INGRESS,
                node_status=NodeStatus.SUCCESS,
                thought_log="Deterministic assistant route completed without financial analysis.",
            ))
            return JSONResponse(status_code=200, content={"status": "COMPLETED", "reply_text": reply_text})

    # 2. Build inputs
    inputs = []
    if content:
        inputs.append({"type": "text", "content": content})

    if not inputs:
        inputs.append({"type": "text", "content": "ขอตรวจสอบสภาพคล่องทางการเงิน"})

    # 3. Process via MasterOrchestrator
    profile_context = payload.profile_context.model_dump() if payload.profile_context else None
    result = await orchestrator.process_session(user_id, inputs, profile_context=profile_context)
    return JSONResponse(status_code=200, content=jsonable_encoder(result))


@app.get("/api/v1/profile")
async def get_user_profile(user_id: str = "sme_user_001"):
    """Fetches real SME business financial profile from MongoDB Atlas."""
    profile = await orchestrator.get_user_financial_profile(user_id)
    return JSONResponse(status_code=200, content=jsonable_encoder(profile))

