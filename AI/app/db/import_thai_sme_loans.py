import os
import re
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from sentence_transformers import SentenceTransformer
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ---------------------------------------------------------------------------
# 1. ROBUST REGEX & METADATA PARSER
# ---------------------------------------------------------------------------
def parse_loan_file(file_path: Path) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    metadata: Dict[str, str] = {}
    content_lines = []
    
    in_content = False
    for line in lines:
        if line.startswith("==="):
            in_content = True
            continue
        if not in_content and ":" in line:
            parts = line.split(":", 1)
            metadata[parts[0].strip()] = parts[1].strip()
        else:
            content_lines.append(line)

    product_name = metadata.get("ชื่อสินเชื่อ/บริการ", file_path.stem.replace("_", " ").title())
    bank = metadata.get("ผู้ให้บริการ", "Financial Institution")
    
    # 1. Type
    parent_dir = file_path.parent.name.lower()
    loan_type = "SME Loan"
    if "od" in parent_dir or "working_capital" in parent_dir:
        loan_type = "OD"
    elif "term_loan" in parent_dir:
        loan_type = "Term Loan"
    elif "leasing" in parent_dir:
        loan_type = "Leasing/Hire Purchase"
    elif "tcg" in parent_dir or "guarantee" in parent_dir or "บสย" in product_name or "tcg" in product_name.lower():
        loan_type = "TCG PGS"

    # 2. Max Limit
    max_limit = 0.0
    for l in content_lines:
        if any(w in l for w in ["วงเงิน:", "วงเงินค้ำต่อราย:", "วงเงินสูงสุด"]):
            m = re.search(r'([\d,]+(?:\.\d+)?)\s*(ล้านบาท|บาท)', l)
            if m:
                val = float(m.group(1).replace(',', ''))
                if m.group(2) == "ล้านบาท":
                    val *= 1_000_000.0
                max_limit = val
                break
    if max_limit == 0.0:
        max_limit = 5_000_000.0  # Fallback if unspecified

    # 3. Interest Rate
    interest_rate = "Subject to bank underwriting"
    for l in content_lines:
        if any(w in l for w in ["อัตราดอกเบี้ย:", "ดอกเบี้ย:"]):
            interest_rate = l.split(":", 1)[-1].strip()
            break

    # 4. Collateral Requirement
    requires_collateral = False
    for l in content_lines:
        if "หลักประกัน:" in l:
            clause = l.split(":", 1)[-1].strip()
            if any(w in clause for w in ["ที่ดิน", "สิ่งปลูกสร้าง", "อสังหาริมทรัพย์", "เงินฝาก", "ต้องใช้หลักทรัพย์"]):
                requires_collateral = True
            elif any(w in clause for w in ["ไม่ต้องใช้", "ไม่มีหลักทรัพย์", "บสย.", "clean loan"]):
                requires_collateral = False

    # 5. Minimum Business Age
    min_age_years = 1.0
    for l in content_lines:
        if any(w in l for w in ["คุณสมบัติ", "ประสบการณ์", "อายุการดำเนินธุรกิจ", "เปิดกิจการ"]):
            m_age = re.search(r'(\d+(?:\.\d+)?)\s*ปี', l)
            if m_age:
                min_age_years = float(m_age.group(1))
                break

    # 6. Minimum Revenue (Extract actual revenue before fallback)
    min_revenue = 0.0
    for l in content_lines:
        if any(k in l for k in ["รายได้ขั้นต่ำ", "ยอดขาย", "รายได้ต่อเดือน", "รายได้ต่อปี"]):
            m_rev = re.search(r'([\d,]+(?:\.\d+)?)\s*(ล้านบาท|บาท)', l)
            if m_rev:
                val = float(m_rev.group(1).replace(',', ''))
                if m_rev.group(2) == "ล้านบาท":
                    val = (val * 1_000_000.0) / 12.0  # Convert annual revenue to monthly
                elif "ปี" in l:
                    val /= 12.0
                min_revenue = val
                break

    if min_revenue == 0.0:
        # Fallback based on risk category
        min_revenue = 50_000.0 if not requires_collateral else 100_000.0

    # 7. Required Documents
    docs = ["VAT returns (PP.30) past 6 months", "Bank Statement past 6 months", "National ID card copy"]
    for l in content_lines:
        if "เอกสาร" in l:
            parts = l.split(":", 1)[-1].split(",")
            clean_docs = [p.strip() for p in parts if len(p.strip()) > 3]
            if clean_docs:
                docs = clean_docs
            break

    full_content = " ".join(content_lines)[:1200]
    file_id = f"loan_{file_path.stem}"

    return {
        "id": file_id,
        "bank": bank,
        "product_name": product_name,
        "content": full_content,
        "type": loan_type,
        "interest_rate": interest_rate,
        "max_limit": max_limit,
        "extra_rules": {
            "min_revenue": round(min_revenue, 2),
            "min_age_years": min_age_years,
            "requires_collateral": requires_collateral
        },
        "required_documents": docs,
        "source_file": str(file_path.name)
    }

# ---------------------------------------------------------------------------
# 2. CONTEXTUAL ENRICHMENT GENERATOR (Satellite LLM)
# ---------------------------------------------------------------------------
async def generate_contextual_prefix(doc: Dict[str, Any]) -> str:
    """
    Uses Satellite Worker LLM (qwen3:1.7b) to generate a concise Contextual Summary Header
    prefixed to document chunks under Contextual RAG principles.
    """
    rules = doc["extra_rules"]
    col_str = "Requires physical collateral" if rules["requires_collateral"] else "No collateral required (Clean Loan / TCG Guarantee)"
    
    prompt = (
        f"Write a 1-sentence concise context summary of this SME loan to guide RAG vector retrieval: "
        f"Product: {doc['product_name']}, Bank: {doc['bank']}, Type: {doc['type']}, "
        f"Max Limit: {doc['max_limit']:,.0f} THB, Collateral: {col_str}, "
        f"Min Revenue: {rules['min_revenue']:,.0f} THB/month, Min Age: {rules['min_age_years']} years"
    )
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                f"{settings.OLLAMA_BASE_URL}/chat/completions",
                json={
                    "model": settings.OLLAMA_WORKER_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are an AI loan context summarizer. Reply with a single concise sentence in English without conversational prefixes."},
                        {"role": "user", "content": prompt}
                    ],
                    "options": {"temperature": 0.0}
                }
            )
            if res.status_code == 200:
                summary = res.json()["choices"][0]["message"]["content"].strip()
                return f"[Product Context: {summary}]"
    except Exception:
        pass

    # Deterministic Contextual Fallback if LLM does not respond
    return f"[Product Context: {doc['product_name']} by {doc['bank']} type {doc['type']} limit {doc['max_limit']:,.0f} THB ({col_str})]"

# ---------------------------------------------------------------------------
# 3. PIPELINE MAIN RUNNER
# ---------------------------------------------------------------------------
async def import_all_thai_sme_loans(loans_dir: str = "thai_sme_loans"):
    loans_path = Path(loans_dir)
    if not loans_path.exists():
        print(f"❌ Error: Directory '{loans_dir}' not found!")
        return

    txt_files = [f for f in loans_path.rglob("*.txt") if "EXPIRED" not in f.name]
    print(f"📁 Found {len(txt_files)} valid loan files in '{loans_dir}'")

    print("🚀 [1/3] Loading embedding model: intfloat/multilingual-e5-small...")
    model = SentenceTransformer("intfloat/multilingual-e5-small")

    print(f"📡 [2/3] Connecting to MongoDB Atlas ({settings.MONGO_DB_NAME})...")
    client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=10000)
    db = client[settings.MONGO_DB_NAME]
    collection = db["loan_products"]

    print("⚡ [3/3] Generating contextual prefixes, creating 384-dim embeddings, and upserting into MongoDB...")
    now = datetime.now(timezone.utc)
    success_count = 0

    for idx, f in enumerate(txt_files, 1):
        try:
            loan_doc = parse_loan_file(f)

            # 1. Contextual RAG Enrichment
            context_prefix = await generate_contextual_prefix(loan_doc)
            loan_doc["contextual_summary"] = context_prefix

            # 2. Combine contextual prefix with content before encoding
            passage_text = (
                f"passage: {context_prefix} {loan_doc['product_name']} {loan_doc['bank']} "
                f"{loan_doc['content']} type {loan_doc['type']} interest {loan_doc['interest_rate']}"
            )
            vector = model.encode(passage_text, normalize_embeddings=True).tolist()
            loan_doc["embedding"] = vector
            loan_doc["updated_at"] = now

            # 3. Upsert into MongoDB
            await collection.update_one(
                {"id": loan_doc["id"]},
                {"$set": loan_doc},
                upsert=True
            )
            success_count += 1
            print(f"   [{idx:02d}/{len(txt_files)}] ✅ {loan_doc['id']} -> {loan_doc['product_name'][:35]} | {context_prefix[:45]}...")
        except Exception as e:
            print(f"   [{idx:02d}/{len(txt_files)}] ❌ Error processing {f.name}: {e}")

    total_in_db = await collection.count_documents({})
    print(f"\n🎉 Successfully imported {success_count} products! Total in DB: {total_in_db}")
    client.close()

if __name__ == "__main__":
    asyncio.run(import_all_thai_sme_loans())