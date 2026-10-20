from typing import List, Optional, Literal
from pydantic import BaseModel, Field

# =====================================================================
# COMMON SUB-SCHEMAS
# =====================================================================

class SellerBuyerSchema(BaseModel):
    name: Optional[str] = None
    tax_id: Optional[str] = None

class LineItemSchema(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = 1.0
    unit_price: Optional[float] = 0.0
    amount: Optional[float] = 0.0

# =====================================================================
# 1. PAYMENT SLIP
# =====================================================================

class PaymentSlipSchema(BaseModel):
    doc_type: Literal["payment_slip"] = "payment_slip"
    extraction_confidence: Optional[float] = None
    needs_human_review: bool = False
    review_reasons: List[str] = Field(default_factory=list)
    unreadable_fields: List[str] = Field(default_factory=list)
    
    transaction_datetime: Optional[str] = None
    date_format: Optional[str] = None
    reference_no: Optional[str] = None
    status_text: Optional[str] = None
    amount: Optional[float] = 0.0
    currency: str = "THB"
    sender_name: Optional[str] = None
    sender_account_masked: Optional[str] = None
    receiver_name: Optional[str] = None
    receiver_account_masked: Optional[str] = None
    memo: Optional[str] = None

# =====================================================================
# 2. INVOICE OR BILL
# =====================================================================

class InvoiceOrBillSchema(BaseModel):
    doc_type: Literal["invoice_or_bill"] = "invoice_or_bill"
    extraction_confidence: Optional[float] = None
    needs_human_review: bool = False
    review_reasons: List[str] = Field(default_factory=list)
    is_handwritten: bool = False
    unreadable_fields: List[str] = Field(default_factory=list)
    
    document_type_text: Optional[str] = None
    document_no: Optional[str] = None
    issue_date: Optional[str] = None
    date_format: Optional[str] = None
    due_date: Optional[str] = None
    credit_term_days: Optional[int] = None
    currency: str = "THB"
    
    seller: Optional[SellerBuyerSchema] = None
    buyer: Optional[SellerBuyerSchema] = None
    line_items: List[LineItemSchema] = Field(default_factory=list)
    
    subtotal: Optional[float] = 0.0
    discount_total: Optional[float] = 0.0
    vat_amount: Optional[float] = 0.0
    vat_included: Optional[bool] = False
    withholding_tax_amount: Optional[float] = 0.0
    grand_total: Optional[float] = 0.0

# =====================================================================
# 3. BANK STATEMENT
# =====================================================================

class StatementAccountSchema(BaseModel):
    bank: Optional[str] = None
    account_holder: Optional[str] = None
    account_masked: Optional[str] = None
    currency: str = "THB"
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    balance_forward: Optional[float] = None
    closing_balance: Optional[float] = None

class StatementTransactionSchema(BaseModel):
    date: Optional[str] = None
    code: Optional[str] = None
    channel: Optional[str] = None
    description: Optional[str] = None
    withdrawal: Optional[float] = None
    deposit: Optional[float] = None
    amount: Optional[float] = 0.0
    balance: Optional[float] = 0.0
    reference_code: Optional[str] = None

class BankStatementSchema(BaseModel):
    doc_type: Literal["bank_statement"] = "bank_statement"
    extraction_confidence: Optional[float] = None
    needs_human_review: bool = False
    review_reasons: List[str] = Field(default_factory=list)
    unreadable_fields: List[str] = Field(default_factory=list)
    bank_format: Optional[str] = None
    date_format: Optional[str] = None
    
    account: Optional[StatementAccountSchema] = None
    transactions: List[StatementTransactionSchema] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
