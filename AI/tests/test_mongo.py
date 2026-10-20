import pytest
from app.db.mongo import MongoDBManager
from app.db.vector_store import LoanVectorStore

def test_mongo_manager_attributes():
    manager = MongoDBManager(uri="mongodb://localhost:27017", db_name="test_fintech")
    assert manager.db_name == "test_fintech"
    assert manager.receipts_col_name == "receipts"
    assert manager.statements_col_name == "statements"
    assert manager.loan_products_col_name == "loan_products"
    assert manager.sessions_col_name == "sessions"

@pytest.mark.asyncio
async def test_hybrid_vector_store():
    store = LoanVectorStore()
    results = await store.hybrid_search("OD วงเงินเบิกเกินบัญชี", limit=3)
    assert len(results) > 0
    assert any("OD" in r.get("type", "") or "OD" in r.get("product_name", "") for r in results)
