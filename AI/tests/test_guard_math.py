import pytest
from app.core.guard import InvariantSanityGuard
from app.schemas.financial import InvoiceOrBillSchema, LineItemSchema

def test_guard_vat_exclusive_with_wht():
    guard = InvariantSanityGuard()
    # Subtotal 10,000, VAT 7% = 700, WHT 3% (service) = 300
    # Grand Total = 10,000 + 700 - 300 = 10,400
    invoice = InvoiceOrBillSchema(
        document_no="INV-EXC-01",
        subtotal=10000.0,
        discount_total=0.0,
        vat_included=False,
        vat_amount=700.0,
        withholding_tax_amount=300.0,
        grand_total=10400.0,
        line_items=[LineItemSchema(description="ค่าบริการซ่อม", quantity=1, unit_price=10000.0, amount=10000.0)]
    )
    result = guard.verify_receipt_math(invoice)
    assert result.is_valid is True

def test_guard_vat_inclusive_calculation():
    guard = InvariantSanityGuard()
    # 10,700 inclusive of VAT 7% -> VAT = 10,700 * 7 / 107 = 700
    invoice = InvoiceOrBillSchema(
        document_no="INV-INC-01",
        subtotal=10700.0,
        discount_total=0.0,
        vat_included=True,
        vat_amount=700.0,
        withholding_tax_amount=0.0,
        grand_total=10700.0,
        line_items=[LineItemSchema(description="อะไหล่", quantity=1, unit_price=10700.0, amount=10700.0)]
    )
    result = guard.verify_receipt_math(invoice)
    assert result.is_valid is True

def test_guard_detects_vat_mismatch():
    guard = InvariantSanityGuard()
    invoice = InvoiceOrBillSchema(
        document_no="INV-ERR-01",
        subtotal=10000.0,
        vat_included=False,
        vat_amount=950.0,  # Deliberate wrong VAT (should be 700)
        grand_total=10950.0,
        line_items=[LineItemSchema(description="สินค้า", quantity=1, unit_price=10000.0, amount=10000.0)]
    )
    result = guard.verify_receipt_math(invoice)
    assert result.is_valid is False
    assert result.error_code == "VAT_CALCULATION_MISMATCH"
    assert "700" in result.feedback_prompt

def test_guard_cashflow_alignment():
    guard = InvariantSanityGuard()
    # 120,000 cash - 95,000 expense = 25,000 projected cash.
    result = guard.verify_cashflow_alignment(
        current_cash=120000.0,
        expense=95000.0,
        projected_cash=25000.0,
        stated_runway=8.3,
        actual_runway=8.3
    )
    assert result.is_valid is True

    # Stated runway discrepancy
    err_result = guard.verify_cashflow_alignment(
        current_cash=120000.0,
        expense=95000.0,
        projected_cash=25000.0,
        stated_runway=30.0,  # Hallucinated 30 days
        actual_runway=8.3
    )
    assert err_result.is_valid is False
    assert err_result.error_code == "RUNWAY_MISMATCH"

def test_guard_policy_completeness():
    guard = InvariantSanityGuard()
    # Runway < 15 days without warning keywords should fail
    bad_draft = "ยอดค่าใช้จ่ายของคุณได้รับการบันทึกเรียบร้อยแล้วครับ ขอบคุณครับ"
    res = guard.verify_policy_completeness(runway_days=10.0, is_debt_risk=False, draft_text=bad_draft)
    assert res.is_valid is False
    assert res.error_code == "POLICY_LIQUIDITY_WARNING_MISSING"

    # Draft with warning keywords should pass
    good_draft = "ตรวจพบความเสี่ยงสภาพคล่องคงเหลือเพียง 10 วัน แนะนำให้พิจารณาชะลอการจ่ายหรือขอสินเชื่อหมุนเวียน"
    res_good = guard.verify_policy_completeness(runway_days=10.0, is_debt_risk=False, draft_text=good_draft)
    assert res_good.is_valid is True
