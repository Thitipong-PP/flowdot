import pytest
from app.workers.loan_worker import LoanWorker
from app.db.vector_store import LoanVectorStore

@pytest.mark.asyncio
async def test_hybrid_rrf_search():
    store = LoanVectorStore()
    results = await store.hybrid_search("OD วงเงินเบิกเกินบัญชี บสย", limit=3)
    assert len(results) > 0
    types = [p["type"] for p in results]
    assert any("OD" in t or "บสย" in t for t in types)

@pytest.mark.asyncio
async def test_deterministic_grader_filters_ineligible():
    worker = LoanWorker()
    # Profile: New shop (0.5 years), no collateral, low revenue 30,000
    profile = {"monthly_revenue": 30000.0, "business_age_years": 0.5, "has_collateral": False}
    ratios = {"dscr": 1.2, "dti": 0.3}
    
    matches = await worker.match_loans(deficit=40000.0, ratios=ratios, profile=profile)
    # Secured loan (req: age 3y, rev 200k, collateral) must be filtered out
    for m in matches:
        assert m.get("extra_rules", {}).get("requires_collateral") is not True

@pytest.mark.asyncio
async def test_crag_recovery_loop_on_collateral_rejection():
    worker = LoanWorker()
    profile = {"monthly_revenue": 120000.0, "business_age_years": 2.0, "has_collateral": False}
    ratios = {"dscr": 1.5, "dti": 0.2}
    
    # Trigger matching: should diagnose that collateral is missing and recover with Clean Loan / บสย.
    matches = await worker.match_loans(deficit=50000.0, ratios=ratios, profile=profile)
    assert len(matches) > 0
    assert any("บสย" in m["product_name"] or "Clean" in m["product_name"] or "OD" in m["product_name"] for m in matches)
    assert "required_documents" in matches[0]
