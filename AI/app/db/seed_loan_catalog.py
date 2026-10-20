import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

# 5 Core Thai SME Loan Catalog policies
RAW_LOAN_POLICIES: List[Dict[str, Any]] = [
    {
        "id": "loan_od_01",
        "bank": "Kasikornbank",
        "product_name": "KBANK SME Quick OD Limit",
        "content": "Kasikornbank SME Quick OD Limit วงเงินเบิกเกินบัญชีสำหรับเสริมสภาพคล่องฉุกเฉิน หมุนเวียนระยะสั้น จ่ายดอกเบี้ยตามจริงที่ใช้ อัตราดอกเบี้ย MRR + 2.5%",
        "type": "OD",
        "interest_rate": "MRR + 2.5%",
        "max_limit": 5000000.0,
        "extra_rules": {
            "min_revenue": 100000.0,
            "min_age_years": 1.0,
            "requires_collateral": False
        },
        "required_documents": [
            "ภ.พ.30 ย้อนหลัง 6 เดือน",
            "Bank Statement ย้อนหลัง 6 เดือน",
            "หนังสือรับรองบริษัท (อายุไม่เกิน 3 เดือน)"
        ]
    },
    {
        "id": "loan_pgs_02",
        "bank": "SME D Bank",
        "product_name": "สินเชื่อ บสย. PGS ค้ำประกันเต็มวงเงิน",
        "content": "SME D Bank สินเชื่อ บสย. PGS โครงการค้ำประกันสินเชื่อเพื่อผู้ประกอบการที่ขาดหลักประกัน Clean Loan รัฐบาลสนับสนุนค่าธรรมเนียมค้ำประกัน",
        "type": "บสย. PGS",
        "interest_rate": "MLR - 1.0%",
        "max_limit": 3000000.0,
        "extra_rules": {
            "min_revenue": 50000.0,
            "min_age_years": 1.0,
            "requires_collateral": False
        },
        "required_documents": [
            "สำเนาบัตรประชาชนกรรมการผู้มีอำนาจ",
            "หนังสือยินยอมให้ บสย. ตรวจสอบข้อมูล",
            "Bank Statement ย้อนหลัง 6 เดือน"
        ]
    },
    {
        "id": "loan_factoring_03",
        "bank": "Krungsri",
        "product_name": "Krungsri Invoice Factoring Express",
        "content": "Krungsri Factoring รับซื้อหนี้การค้า เปลี่ยนใบแจ้งหนี้เป็นเงินสดทันที รับเงินล่วงหน้าสูงสุด 85-90% เหมาะสำหรับธุรกิจ B2B ที่รอเก็บเงินลูกค้า",
        "type": "Factoring",
        "interest_rate": "6.5% ต่อปี",
        "max_limit": 10000000.0,
        "extra_rules": {
            "min_revenue": 80000.0,
            "min_age_years": 1.0,
            "requires_collateral": False
        },
        "required_documents": [
            "สำเนาใบแจ้งหนี้ / ใบกำกับภาษี / ใบส่งของ",
            "สัญญาการค้ากับคู่ค้า (Trade Contract)",
            "Bank Statement ย้อนหลัง 3 เดือน"
        ]
    },
    {
        "id": "loan_clean_04",
        "bank": "SCB",
        "product_name": "SCB SME Clean Loan สบายใจ",
        "content": "SCB สินเชื่อธุรกิจไม่มีหลักทรัพย์ค้ำประกัน Clean Loan ดอกเบี้ยพิเศษ ไม่ต้องใช้ที่ดินหรือเงินฝากค้ำ อนุมัติไวภายใน 3 วันทำการ",
        "type": "Clean Loan",
        "interest_rate": "MRR + 3.0%",
        "max_limit": 2000000.0,
        "extra_rules": {
            "min_revenue": 150000.0,
            "min_age_years": 2.0,
            "requires_collateral": False
        },
        "required_documents": [
            "งบการเงินย้อนหลัง 1 ปี",
            "ภ.พ.30 ย้อนหลัง 6 เดือน",
            "Bank Statement ย้อนหลัง 6 เดือน"
        ]
    },
    {
        "id": "loan_secured_05",
        "bank": "Bangkok Bank",
        "product_name": "BBL บัวหลวงพารวย (ใช้หลักประกัน)",
        "content": "Bangkok Bank BBL สินเชื่อขยายกิจการ ใช้ที่ดิน อาคารพาณิชย์ หรือสิ่งปลูกสร้างค้ำประกัน ดอกเบี้ยต่ำพิเศษ วงเงินสูงสุด 30 ล้านบาท ผ่อนนานสูงสุด 10 ปี",
        "type": "Secured Loan",
        "interest_rate": "MRR + 1.25%",
        "max_limit": 30000000.0,
        "extra_rules": {
            "min_revenue": 200000.0,
            "min_age_years": 3.0,
            "requires_collateral": True
        },
        "required_documents": [
            "โฉนดที่ดิน / สำเนาหลักทรัพย์ค้ำประกัน",
            "งบการเงินย้อนหลัง 3 ปี",
            "ภ.พ.30 และ Statement ย้อนหลัง 12 เดือน"
        ]
    }
]

async def seed_loan_products():
    print("🚀 [1/3] Loading Embedding Model: intfloat/multilingual-e5-small...")
    model = SentenceTransformer("intfloat/multilingual-e5-small")

    print(f"📡 [2/3] Connecting to MongoDB Atlas ({settings.MONGO_DB_NAME})...")
    client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=10000)
    db = client[settings.MONGO_DB_NAME]
    collection = db["loan_products"]

    print("⚡ [3/3] Generating 384-dimensional Embeddings & Upserting to Atlas...")
    now = datetime.now(timezone.utc)

    for p in RAW_LOAN_POLICIES:
        # Standard E5 document ingestion prefix: 'passage: '
        passage_text = f"passage: {p['product_name']} {p['bank']} {p['content']} {p['type']} ดอกเบี้ย {p['interest_rate']}"
        vector = model.encode(passage_text, normalize_embeddings=True).tolist()

        doc = {
            "id": p["id"],
            "bank": p["bank"],
            "product_name": p["product_name"],
            "content": p["content"],
            "type": p["type"],
            "interest_rate": p["interest_rate"],
            "max_limit": p["max_limit"],
            "extra_rules": p["extra_rules"],
            "required_documents": p["required_documents"],
            "embedding": vector,
            "updated_at": now
        }

        # Upsert by unique product ID
        await collection.update_one(
            {"id": p["id"]},
            {"$set": doc},
            upsert=True
        )
        print(f"   ✅ Upserted: {p['id']} - {p['product_name']} (Dim: {len(vector)})")

    total = await collection.count_documents({})
    print(f"\n🎉 Successfully seeded {len(RAW_LOAN_POLICIES)} policies! Total in DB: {total}")
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_loan_products())
