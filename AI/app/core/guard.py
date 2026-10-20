from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.financial import InvoiceOrBillSchema

class InvariantResult(BaseModel):
    is_valid: bool
    error_code: Optional[str] = None
    violation_type: Optional[str] = None
    feedback_prompt: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)

class InvariantSanityGuard:
    """Pure Python Deterministic Guard for Financial Math & Policy Invariants."""
    TOLERANCE = Decimal("0.05")

    def verify_receipt_math(self, invoice: InvoiceOrBillSchema) -> InvariantResult:
        """Verifies receipt math: line items, VAT (Inclusive/Exclusive), Withholding Tax, and Grand Total."""
        subtotal = Decimal(str(invoice.subtotal or 0.0))
        discount = Decimal(str(invoice.discount_total or 0.0))
        vat_amount = Decimal(str(invoice.vat_amount or 0.0))
        wht_amount = Decimal(str(invoice.withholding_tax_amount or 0.0))
        grand_total = Decimal(str(invoice.grand_total or 0.0))

        # Invariant 1: Check Line Items math (quantity * unit_price == amount)
        if invoice.line_items:
            for idx, item in enumerate(invoice.line_items, 1):
                qty = Decimal(str(item.quantity or 1.0))
                price = Decimal(str(item.unit_price or 0.0))
                amt = Decimal(str(item.amount or 0.0))
                expected_amt = (qty * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if abs(amt - expected_amt) > self.TOLERANCE:
                    return InvariantResult(
                        is_valid=False,
                        error_code="ITEM_LINE_MATH_MISMATCH",
                        violation_type="MATH_VIOLATION",
                        feedback_prompt=f"รายการที่ {idx} ({item.description}): คำนวณจำนวน ({qty}) x ราคา ({price}) = {expected_amt} บาท แต่ยอดที่ระบุคือ {amt} บาท โปรดปรับยอดให้ตรงกัน",
                        details={"item_index": idx, "expected": float(expected_amt), "actual": float(amt)}
                    )

            # Invariant 2: Check sum of line items == subtotal
            items_sum = sum(Decimal(str(item.amount or 0.0)) for item in invoice.line_items)
            if abs(items_sum - subtotal) > self.TOLERANCE:
                return InvariantResult(
                    is_valid=False,
                    error_code="SUBTOTAL_LINE_ITEM_MISMATCH",
                    violation_type="MATH_VIOLATION",
                    feedback_prompt=f"ผลรวมของรายการสินค้า ({items_sum} บาท) ไม่ตรงกับยอด Subtotal ({subtotal} บาท)",
                    details={"items_sum": float(items_sum), "subtotal": float(subtotal)}
                )

        # Invariant 3: VAT Verification (Inclusive vs Exclusive)
        taxable_base = subtotal - discount
        if taxable_base > 0 and vat_amount > 0:
            if invoice.vat_included:
                # VAT Inclusive: Grand Total * 7 / 107
                expected_vat = (grand_total * Decimal("7") / Decimal("107")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                # VAT Exclusive: Taxable Base * 7%
                expected_vat = (taxable_base * Decimal("0.07")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            if abs(vat_amount - expected_vat) > self.TOLERANCE:
                vat_mode_str = "รวมใน (Inclusive)" if invoice.vat_included else "แยกนอก (Exclusive)"
                return InvariantResult(
                    is_valid=False,
                    error_code="VAT_CALCULATION_MISMATCH",
                    violation_type="MATH_VAT_MISMATCH",
                    feedback_prompt=f"การคำนวณ VAT แบบ {vat_mode_str} ไม่ถูกต้อง: ยอดที่ควรจะเป็นคือประมาณ {expected_vat} บาท แต่ในเอกสารระบุ {vat_amount} บาท",
                    details={"expected_vat": float(expected_vat), "actual_vat": float(vat_amount), "vat_included": invoice.vat_included}
                )

        # Invariant 4: Net Grand Total Formula: Grand Total = Subtotal - Discount + VAT - Withholding Tax
        if invoice.vat_included:
            # When price already includes VAT: Grand Total = Subtotal - Discount - Withholding Tax
            expected_grand_total = subtotal - discount - wht_amount
        else:
            # When price excludes VAT: Grand Total = Subtotal - Discount + VAT - Withholding Tax
            expected_grand_total = subtotal - discount + vat_amount - wht_amount

        if abs(grand_total - expected_grand_total) > self.TOLERANCE:
            return InvariantResult(
                is_valid=False,
                error_code="GRAND_TOTAL_FORMULA_MISMATCH",
                violation_type="MATH_TOTAL_MISMATCH",
                feedback_prompt=(
                    f"ยอดรวมสุทธิ (Grand Total) คำนวณไม่ถูกต้อง: "
                    f"Subtotal({subtotal}) - Discount({discount}) + VAT({vat_amount}) - WHT({wht_amount}) "
                    f"ควรได้ยอดสุทธิ {expected_grand_total} บาท แต่ผลลัพธ์ระบุ {grand_total} บาท"
                ),
                details={"expected_grand_total": float(expected_grand_total), "actual_grand_total": float(grand_total)}
            )

        return InvariantResult(is_valid=True)

    def verify_cashflow_alignment(
        self,
        current_cash: float,
        expense: float = 0.0,
        projected_cash: float = 0.0,
        stated_runway: float = 0.0,
        actual_runway: float = 0.0,
        income: float = 0.0
    ) -> InvariantResult:
        """Verifies that Orchestrator draft numbers strictly match Cashflow Simulator output."""
        calc_projected = current_cash + income - expense
        if abs(calc_projected - projected_cash) > 0.01:
            return InvariantResult(
                is_valid=False,
                error_code="CASHFLOW_ARITHMETIC_ERROR",
                violation_type="CASHFLOW_MISMATCH",
                feedback_prompt=f"ยอดเงินคงเหลือคำนวณคลาดเคลื่อน: {current_cash} + {income} - {expense} = {calc_projected} แต่ข้อความระบุ {projected_cash}",
                details={"expected_projected": calc_projected, "actual_projected": projected_cash}
            )

        if abs(stated_runway - actual_runway) > 0.1:
            return InvariantResult(
                is_valid=False,
                error_code="RUNWAY_MISMATCH",
                violation_type="RUNWAY_MISMATCH",
                feedback_prompt=f"จำนวนวันสภาพคล่องคงเหลือ (Runway) ในข้อความ ({stated_runway} วัน) ไม่ตรงกับผลลัพธ์ Simulator ({actual_runway} วัน)",
                details={"expected_runway": actual_runway, "stated_runway": stated_runway}
            )

        return InvariantResult(is_valid=True)

    def verify_statement_math(
        self,
        balance_forward: Optional[float],
        closing_balance: Optional[float],
        total_deposit: float,
        total_withdrawal: float
    ) -> InvariantResult:
        """Verifies Bank Statement invariant: Closing Balance == Balance Forward + Deposits - Withdrawals."""
        if balance_forward is not None and closing_balance is not None:
            expected_closing = round(balance_forward + total_deposit - total_withdrawal, 2)
            if abs(expected_closing - closing_balance) > 1.0:
                return InvariantResult(
                    is_valid=False,
                    error_code="STATEMENT_BALANCE_MISMATCH",
                    violation_type="MATH_STATEMENT_MISMATCH",
                    feedback_prompt=f"ยอดรวมใน Statement ไม่ลงตัว: ยอดยกมา ({balance_forward:,.2f}) + เงินเข้า ({total_deposit:,.2f}) - เงินออก ({total_withdrawal:,.2f}) = {expected_closing:,.2f} แต่ยอดคงเหลือระบุ {closing_balance:,.2f}",
                    details={"expected": expected_closing, "actual": closing_balance}
                )
        return InvariantResult(is_valid=True)

    def verify_policy_completeness(
        self,
        runway_days: float,
        is_debt_risk: bool,
        draft_text: str
    ) -> InvariantResult:
        """Verifies policy rules: e.g. crisis warning and financing solutions when runway is critical."""
        if runway_days < 15.0:
            # Draft must contain warning terminology
            warning_keywords = ["เสี่ยง", "สภาพคล่อง", "วิกฤต", "ระวัง", "สินเชื่อ", "ชะลอ"]
            if not any(k in draft_text for k in warning_keywords):
                return InvariantResult(
                    is_valid=False,
                    error_code="POLICY_LIQUIDITY_WARNING_MISSING",
                    violation_type="POLICY_VIOLATION",
                    feedback_prompt="สภาพคล่องเหลือน้อยกว่า 15 วัน แต่ในร่างข้อความยังไม่มีคำเตือนความเสี่ยงสภาพคล่องหรือข้อเสนอแนะแหล่งเงินทุน โปรดระบุคำเตือนให้ชัดเจน"
                )

        if is_debt_risk:
            debt_keywords = ["หนี้", "ผิดนัด", "ชำระหนี้", "เงินไม่พอจ่าย"]
            if not any(k in draft_text for k in debt_keywords):
                return InvariantResult(
                    is_valid=False,
                    error_code="POLICY_DEBT_RISK_WARNING_MISSING",
                    violation_type="POLICY_VIOLATION",
                    feedback_prompt="ตรวจพบความเสี่ยงเงินไม่พอจ่ายหนี้สิ้นเดือน แต่ในร่างคำตอบยังไม่มีการแจ้งเตือนเรื่องภาระหนี้ โปรดเพิ่มคำเตือนหนี้สิ้นเดือน"
                )

        return InvariantResult(is_valid=True)
