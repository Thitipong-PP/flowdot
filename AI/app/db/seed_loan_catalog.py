import sys
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sentence_transformers import SentenceTransformer
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

# 5 Core Thai SME Loan Catalog policies
RAW_LOAN_POLICIES: List[Dict[str, Any]] = [
    {
        "id": "loan_od_01",
        "bank": "Kasikornbank",
        "product_name": "KBANK SME Quick OD Limit",
        "content": "Kasikornbank SME Quick OD Limit - Overdraft facility for emergency liquidity and short-term working capital. Pay interest only on drawn funds at MRR + 2.5%.",
        "type": "OD",
        "interest_rate": "MRR + 2.5%",
        "max_limit": 5000000.0,
        "extra_rules": {
            "min_revenue": 100000.0,
            "min_age_years": 1.0,
            "requires_collateral": False
        },
        "required_documents": [
            "VAT returns (PP.30) past 6 months",
            "Bank statements past 6 months",
            "Company registration certificate (within 3 months)"
        ]
    },
    {
        "id": "loan_pgs_02",
        "bank": "SME D Bank",
        "product_name": "TCG PGS Full Credit Guarantee Loan",
        "content": "SME D Bank TCG PGS Loan - Credit guarantee program for SMEs lacking physical collateral. Clean loan supported by Thai Credit Guarantee Corporation with government subsidized guarantee fee.",
        "type": "TCG PGS",
        "interest_rate": "MLR - 1.0%",
        "max_limit": 3000000.0,
        "extra_rules": {
            "min_revenue": 50000.0,
            "min_age_years": 1.0,
            "requires_collateral": False
        },
        "required_documents": [
            "National ID card copy of authorized directors",
            "Consent letter for TCG credit verification",
            "Bank statements past 6 months"
        ]
    },
    {
        "id": "loan_factoring_03",
        "bank": "Krungsri",
        "product_name": "Krungsri Invoice Factoring Express",
        "content": "Krungsri Factoring - Accounts receivable factoring. Convert unpaid customer invoices into immediate cash up to 85-90% advance rate. Ideal for B2B trade awaiting payment collections.",
        "type": "Factoring",
        "interest_rate": "6.5% p.a.",
        "max_limit": 10000000.0,
        "extra_rules": {
            "min_revenue": 80000.0,
            "min_age_years": 1.0,
            "requires_collateral": False
        },
        "required_documents": [
            "Invoice copies / tax invoices / delivery orders",
            "Trade contract with corporate buyer",
            "Bank statements past 3 months"
        ]
    },
    {
        "id": "loan_clean_04",
        "bank": "SCB",
        "product_name": "SCB SME Clean Loan",
        "content": "SCB Unsecured SME Clean Loan with competitive interest rates. No land, property, or fixed deposit collateral required. Fast approval within 3 business days.",
        "type": "Clean Loan",
        "interest_rate": "MRR + 3.0%",
        "max_limit": 2000000.0,
        "extra_rules": {
            "min_revenue": 150000.0,
            "min_age_years": 2.0,
            "requires_collateral": False
        },
        "required_documents": [
            "Financial statements past 1 year",
            "VAT returns (PP.30) past 6 months",
            "Bank statements past 6 months"
        ]
    },
    {
        "id": "loan_secured_05",
        "bank": "Bangkok Bank",
        "product_name": "BBL Bualuang Prosperity Loan (Secured)",
        "content": "Bangkok Bank BBL Business Expansion Loan secured by commercial property, land, or buildings. Prime low interest rates, up to 30 million THB credit limit, and repayment tenor up to 10 years.",
        "type": "Secured Loan",
        "interest_rate": "MRR + 1.25%",
        "max_limit": 30000000.0,
        "extra_rules": {
            "min_revenue": 200000.0,
            "min_age_years": 3.0,
            "requires_collateral": True
        },
        "required_documents": [
            "Land title deed / copy of collateral ownership deeds",
            "Financial statements past 3 years",
            "VAT returns (PP.30) and Bank statements past 12 months"
        ]
    }
]

async def seed_loan_products():
    print("[1/3] Loading Embedding Model: intfloat/multilingual-e5-small...")
    model = SentenceTransformer("intfloat/multilingual-e5-small")

    print(f"[2/3] Connecting to MongoDB Atlas ({settings.MONGO_DB_NAME})...")
    client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=10000)
    db = client[settings.MONGO_DB_NAME]
    collection = db["loan_products"]

    print("[3/3] Generating 384-dimensional Embeddings & Upserting to Atlas...")
    now = datetime.now(timezone.utc)

    for p in RAW_LOAN_POLICIES:
        # Standard E5 document ingestion prefix: 'passage: '
        passage_text = f"passage: {p['product_name']} {p['bank']} {p['content']} {p['type']} interest {p['interest_rate']}"
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
        print(f"   Upserted: {p['id']} - {p['product_name']} (Dim: {len(vector)})")

    total = await collection.count_documents({})
    print(f"\nSuccessfully seeded {len(RAW_LOAN_POLICIES)} policies! Total in DB: {total}")
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_loan_products())
