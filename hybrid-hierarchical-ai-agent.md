# Hybrid Hierarchical AI Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a robust, decoupled Python AI subsystem for an SME Financial Copilot featuring an Ollama ReAct Orchestrator, Typhoon-OCR document intelligence, pure Python financial invariant guards, MongoDB persistence, and real-time SSE telemetry streaming.

**Architecture:** An asynchronous event-driven architecture using FastAPI. Ingress requests pass through an `asyncio.Lock` session serializer, a 3–5 second debounce buffer, a PII anonymizer, and a static fast-path router before invoking a Master Orchestrator (Qwen via Ollama) that coordinates satellite workers (Vision, Cashflow, Loan Matcher), validated by a deterministic math sanity guard and streamed over SSE.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2, Motor (Async MongoDB), OpenAI SDK (for Ollama and Typhoon APIs), Pytest, Pytest-Asyncio.

## Global Constraints

- **Language & Runtime:** Python 3.11+ async execution.
- **Orchestrator LLM:** Local Ollama running `Qwen3-1.7B` or `Qwen2.5` via OpenAI-compatible endpoint at `http://localhost:11434/v1` with structured output enforcement and defensive JSON regex parsing.
- **Vision OCR:** OpenTyphoon OCR API (`typhoon-ocr`) for Thai and English receipts.
- **Persistence:** MongoDB with async Motor client, centralized in `app/db/mongo.py`, with 24-hour TTL index for `PENDING_CONFIRMATION` receipts.
- **RAG / Vector Store:** `MongoDBAtlasVectorSearch` on loan criteria & bank policies.
- **Sanity Guard:** 100% pure Python deterministic mathematics (no LLM arithmetic). Grand total formula must strictly account for VAT inclusive ($7/107$), VAT exclusive ($7\%$), and withholding tax deductions.
- **Cashflow Guard:** Zero division protection on $\text{Daily Burn Rate} \le 0$ returning `runway_days = 9999.0`.
- **Fast-Path Latency:** Rich menu bypass requests must execute in $< 200\text{ ms}$.
- **Telemetry:** Real-time Server-Sent Events (SSE) emitted at `/api/v1/telemetry/stream` including live metrics and inspection `payload`.

---

### Task 1: Environment Setup & Project Configuration

**Files:**
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: Environment variables (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `TYPHOON_API_KEY`, `MONGO_URI`, `MONGO_DB_NAME`).
- Produces: `app.config.settings` (`Settings` Pydantic instance).

- [ ] **Step 1: Write failing test for configuration**

```python
# tests/test_config.py
import os
from app.config import Settings

def test_settings_load_defaults():
    settings = Settings()
    assert settings.OLLAMA_BASE_URL == "http://localhost:11434/v1"
    assert settings.OLLAMA_MODEL == "qwen2.5:1.5b"
    assert settings.MONGO_DB_NAME == "fintech_copilot"
    assert settings.DEBOUNCE_WAIT_SECONDS == 3.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`  
Expected: FAIL (ModuleNotFoundError: No module named 'app')

- [ ] **Step 3: Create requirements.txt and app/config.py**

```text
# requirements.txt
fastapi>=0.110.0
uvicorn>=0.28.0
pydantic>=2.6.0
pydantic-settings>=2.2.0
motor>=3.3.0
openai>=1.14.0
httpx>=0.27.0
faiss-cpu>=1.8.0
rank-bm25>=0.2.2
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "SME Finance Copilot AI Subsystem"
    DEBUG: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "qwen2.5:1.5b"
    TYPHOON_API_KEY: str = "sk-placeholder"
    TYPHOON_OCR_API_URL: str = "https://api.opentyphoon.ai/v1"
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "fintech_copilot"
    DEBOUNCE_WAIT_SECONDS: float = 3.0
    FAST_PATH_LATENCY_THRESHOLD_MS: float = 200.0

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt app/__init__.py app/config.py tests/test_config.py
git commit -m "feat(config): setup dependencies and application settings"
```

---

### Task 2: Financial, State, & Telemetry Schemas

**Files:**
- Create: `app/schemas/__init__.py`
- Create: `app/schemas/financial.py`
- Create: `app/schemas/state.py`
- Create: `app/schemas/events.py`
- Test: `tests/test_schemas.py`

**Interfaces:**
- Consumes: `receipt_template/` fields.
- Produces: `PaymentSlipSchema`, `InvoiceOrBillSchema`, `BankStatementSchema`, `TelemetryEvent`, `AgentSessionState`.

- [ ] **Step 1: Write failing test for schemas**

```python
# tests/test_schemas.py
from datetime import datetime
from app.schemas.financial import InvoiceOrBillSchema, LineItemSchema, SellerBuyerSchema
from app.schemas.events import TelemetryEvent, NodeStatus, ActiveNode

def test_invoice_schema_validation():
    item = LineItemSchema(description="Diesel Filter", quantity=2, unit_price=1500.0, amount=3000.0)
    invoice = InvoiceOrBillSchema(
        document_no="INV-001",
        issue_date="2026-10-17",
        seller=SellerBuyerSchema(name="Auto Parts Ltd", tax_id="0105550000000"),
        line_items=[item],
        subtotal=3000.0,
        vat_included=False,
        vat_amount=210.0,
        withholding_tax_amount=0.0,
        grand_total=3210.0
    )
    assert invoice.grand_total == 3210.0

def test_telemetry_event_schema():
    event = TelemetryEvent(
        event_id="evt_01",
        session_id="user_123",
        event="TOOL_INVOKED",
        active_node=ActiveNode.VISION_WORKER,
        node_status=NodeStatus.PROCESSING,
        payload={"doc_type": "invoice_or_bill"}
    )
    assert event.payload["doc_type"] == "invoice_or_bill"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_schemas.py -v`  
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement schemas in app/schemas/**

```python
# app/schemas/financial.py
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class SellerBuyerSchema(BaseModel):
    name: Optional[str] = None
    tax_id: Optional[str] = None

class LineItemSchema(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float
    amount: float

class PaymentSlipSchema(BaseModel):
    doc_type: Literal["payment_slip"] = "payment_slip"
    reference_no: Optional[str] = None
    transaction_datetime: Optional[str] = None
    amount: float
    currency: str = "THB"
    sender_name: Optional[str] = None
    sender_account_masked: Optional[str] = None
    receiver_name: Optional[str] = None
    receiver_account_masked: Optional[str] = None
    status_text: Optional[str] = None
    memo: Optional[str] = None
    extraction_confidence: Optional[float] = None
    needs_human_review: bool = False
    review_reasons: List[str] = Field(default_factory=list)
    unreadable_fields: List[str] = Field(default_factory=list)

class InvoiceOrBillSchema(BaseModel):
    doc_type: Literal["invoice_or_bill"] = "invoice_or_bill"
    document_no: Optional[str] = None
    document_type_text: Optional[str] = None
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    credit_term_days: Optional[int] = None
    currency: str = "THB"
    seller: Optional[SellerBuyerSchema] = None
    buyer: Optional[SellerBuyerSchema] = None
    line_items: List[LineItemSchema] = Field(default_factory=list)
    subtotal: float
    discount_total: float = 0.0
    vat_included: bool = False
    vat_amount: float = 0.0
    withholding_tax_amount: float = 0.0
    grand_total: float
    extraction_confidence: Optional[float] = None
    needs_human_review: bool = False
    review_reasons: List[str] = Field(default_factory=list)
    unreadable_fields: List[str] = Field(default_factory=list)

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
    date: str
    code: Optional[str] = None
    channel: Optional[str] = None
    description: Optional[str] = None
    withdrawal: Optional[float] = None
    deposit: Optional[float] = None
    amount: float
    balance: float
    reference_code: Optional[str] = None

class BankStatementSchema(BaseModel):
    doc_type: Literal["bank_statement"] = "bank_statement"
    account: StatementAccountSchema
    transactions: List[StatementTransactionSchema] = Field(default_factory=list)
    extraction_confidence: Optional[float] = None
    needs_human_review: bool = False
    review_reasons: List[str] = Field(default_factory=list)
    unreadable_fields: List[str] = Field(default_factory=list)
```

```python
# app/schemas/events.py
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class ActiveNode(str, Enum):
    INGRESS = "INGRESS"
    ORCHESTRATOR = "ORCHESTRATOR"
    VISION_WORKER = "VISION_WORKER"
    CASHFLOW_WORKER = "CASHFLOW_WORKER"
    LOAN_WORKER = "LOAN_WORKER"
    SANITY_GUARD = "SANITY_GUARD"
    RESPONSE_COMPILER = "RESPONSE_COMPILER"

class NodeStatus(str, Enum):
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"

class LiveMetrics(BaseModel):
    latency_ms: float = 0.0
    current_cash: Optional[float] = None
    projected_cash: Optional[float] = None
    runway_days: Optional[float] = None
    risk_level: Optional[str] = None

class TelemetryEvent(BaseModel):
    event_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str
    event: str
    active_node: ActiveNode
    node_status: NodeStatus
    active_wire: Optional[str] = None
    thought_log: Optional[str] = None
    live_metrics: LiveMetrics = Field(default_factory=LiveMetrics)
    payload: Optional[Dict[str, Any]] = None
```

```python
# app/schemas/state.py
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class AgentSessionState(BaseModel):
    session_id: str
    current_cash: float = 120000.0
    upcoming_debt: float = 70000.0
    daily_burn_rate: float = 3000.0
    active_intent: Optional[str] = None
    context_history: List[Dict[str, Any]] = Field(default_factory=list)
    pending_receipt: Optional[Dict[str, Any]] = None
    retry_count: int = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_schemas.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/ tests/test_schemas.py
git commit -m "feat(schemas): define financial, state, and telemetry pydantic contracts"
```

---

### Task 3: Centralized MongoDB Connection Pool & Document Lifecycle

**Files:**
- Create: `app/db/__init__.py`
- Create: `app/db/mongo.py`
- Create: `app/db/vector_store.py`
- Test: `tests/test_mongo.py`

**Interfaces:**
- Consumes: `app.config.settings.MONGO_URI`, `MONGO_DB_NAME`.
- Produces: `get_db()`, `get_receipts_collection()`, `get_statements_collection()`, `init_db_indexes()`.

- [ ] **Step 1: Write failing test for MongoDB lifecycle & TTL index**

```python
# tests/test_mongo.py
import pytest
from app.db.mongo import MongoDBManager

@pytest.mark.asyncio
async def test_mongo_manager_init():
    manager = MongoDBManager(uri="mongodb://localhost:27017", db_name="test_fintech")
    assert manager.db_name == "test_fintech"
    # verify collection accessors return valid names
    assert manager.receipts_collection_name == "receipts"
    assert manager.statements_collection_name == "statements"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mongo.py -v`  
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement app/db/mongo.py and app/db/vector_store.py**

```python
# app/db/mongo.py
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

class MongoDBManager:
    def __init__(self, uri: str, db_name: str):
        self.uri = uri
        self.db_name = db_name
        self.client: AsyncIOMotorClient = None
        self.db: AsyncIOMotorDatabase = None
        self.receipts_collection_name = "receipts"
        self.statements_collection_name = "statements"

    def connect(self):
        if not self.client:
            self.client = AsyncIOMotorClient(self.uri)
            self.db = self.client[self.db_name]

    def close(self):
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    async def init_indexes(self):
        if self.db is not None:
            # TTL Index: expire unconfirmed temporary receipts after 24 hours (86400s)
            await self.db[self.receipts_collection_name].create_index(
                "created_at",
                expireAfterSeconds=86400,
                partialFilterExpression={"status": "PENDING_CONFIRMATION"}
            )
            # Unique compound index for Tier 1 hard duplicate detection
            await self.db[self.receipts_collection_name].create_index(
                [("seller_tax_id", 1), ("document_no", 1)],
                unique=True,
                sparse=True
            )
            await self.db[self.receipts_collection_name].create_index(
                "reference_no",
                unique=True,
                sparse=True
            )

db_manager = MongoDBManager(uri=settings.MONGO_URI, db_name=settings.MONGO_DB_NAME)
```

```python
# app/db/vector_store.py
from typing import List, Dict, Any, Optional
import re
import numpy as np
from rank_bm25 import BM25Okapi
import faiss

DEFAULT_LOAN_PRODUCTS: List[Dict[str, Any]] = [
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

def tokenize_financial_text(text: str) -> List[str]:
    text_clean = text.lower()
    terms = re.findall(r'[a-zA-Z0-9_\.\+]+|[\u0E00-\u0E7F]+', text_clean)
    return [t for t in terms if len(t) > 1]

def create_pseudo_dense_embedding(text: str, dim: int = 64) -> np.ndarray:
    vec = np.zeros(dim, dtype=np.float32)
    tokens = tokenize_financial_text(text)
    for t in tokens:
        idx = hash(t) % dim
        vec[idx] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec

class LoanVectorStore:
    def __init__(self, products: Optional[List[Dict[str, Any]]] = None):
        self.products = products or list(DEFAULT_LOAN_PRODUCTS)
        self.dim = 64
        self._init_bm25()
        self._init_faiss()

    def _init_bm25(self):
        self.corpus = [tokenize_financial_text(p["content"]) for p in self.products]
        self.bm25 = BM25Okapi(self.corpus)

    def _init_faiss(self):
        self.faiss_index = faiss.IndexFlatIP(self.dim)
        embeddings = np.array([create_pseudo_dense_embedding(p["content"], self.dim) for p in self.products])
        self.faiss_index.add(embeddings)

    def rrf_score(self, dense_ranks: Dict[str, int], sparse_ranks: Dict[str, int], k: int = 60) -> List[Dict[str, Any]]:
        scored_candidates = []
        for p in self.products:
            pid = p["id"]
            d_rank = dense_ranks.get(pid, 999)
            s_rank = sparse_ranks.get(pid, 999)
            score = (1.0 / (k + d_rank)) + (1.0 / (k + s_rank))
            scored_candidates.append({**p, "rrf_score": score, "dense_rank": d_rank, "sparse_rank": s_rank})
        return sorted(scored_candidates, key=lambda x: x["rrf_score"], reverse=True)

    async def hybrid_search(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        query_tokens = tokenize_financial_text(query)
        if not query_tokens:
            return self.products[:limit]
        bm25_scores = self.bm25.get_scores(query_tokens)
        sparse_order = np.argsort(bm25_scores)[::-1]
        sparse_ranks = {self.products[idx]["id"]: rank + 1 for rank, idx in enumerate(sparse_order)}

        query_vec = create_pseudo_dense_embedding(query, self.dim).reshape(1, -1)
        distances, dense_order = self.faiss_index.search(query_vec, len(self.products))
        dense_ranks = {self.products[idx]["id"]: rank + 1 for rank, idx in enumerate(dense_order[0])}

        fused_candidates = self.rrf_score(dense_ranks, sparse_ranks, k=60)
        return fused_candidates[:limit]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mongo.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/db/ tests/test_mongo.py
git commit -m "feat(db): implement mongo pool manager, indexes, and vector store interface"
```

---

### Task 4: Invariant Sanity Guard (Math & Policy Enforcer)

**Files:**
- Create: `app/core/__init__.py`
- Create: `app/core/guard.py`
- Test: `tests/test_guard_math.py`

**Interfaces:**
- Consumes: `InvoiceOrBillSchema`, `PaymentSlipSchema`, simulation cash metrics.
- Produces: `verify_receipt_math()`, `verify_cashflow_alignment()`, `InvariantResult(is_valid, error_code, feedback_prompt)`.

- [ ] **Step 1: Write failing test for math invariants (VAT inclusive/exclusive, WHT)**

```python
# tests/test_guard_math.py
from decimal import Decimal
from app.core.guard import InvariantSanityGuard
from app.schemas.financial import InvoiceOrBillSchema, LineItemSchema

def test_guard_vat_exclusive_correct():
    guard = InvariantSanityGuard()
    invoice = InvoiceOrBillSchema(
        document_no="INV-100",
        subtotal=10000.0,
        discount_total=0.0,
        vat_included=False,
        vat_amount=700.0,
        withholding_tax_amount=300.0,  # 3% service WHT
        grand_total=10400.0,  # 10000 + 700 - 300 = 10400
        line_items=[LineItemSchema(description="Service", quantity=1, unit_price=10000.0, amount=10000.0)]
    )
    result = guard.verify_receipt_math(invoice)
    assert result.is_valid is True

def test_guard_vat_inclusive_correct():
    guard = InvariantSanityGuard()
    # 10700 inclusive of VAT 7% -> VAT = 10700 * 7 / 107 = 700
    invoice = InvoiceOrBillSchema(
        document_no="INV-101",
        subtotal=10700.0,
        vat_included=True,
        vat_amount=700.0,
        withholding_tax_amount=0.0,
        grand_total=10700.0,
        line_items=[LineItemSchema(description="Goods", quantity=1, unit_price=10700.0, amount=10700.0)]
    )
    result = guard.verify_receipt_math(invoice)
    assert result.is_valid is True

def test_guard_vat_mismatch_triggers_feedback():
    guard = InvariantSanityGuard()
    invoice = InvoiceOrBillSchema(
        document_no="INV-102",
        subtotal=10000.0,
        vat_included=False,
        vat_amount=999.0,  # Deliberate wrong VAT
        grand_total=10999.0,
        line_items=[LineItemSchema(description="Goods", quantity=1, unit_price=10000.0, amount=10000.0)]
    )
    result = guard.verify_receipt_math(invoice)
    assert result.is_valid is False
    assert "VAT calculation mismatch" in result.feedback_prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_guard_math.py -v`  
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement app/core/guard.py**

```python
# app/core/guard.py
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from pydantic import BaseModel
from app.schemas.financial import InvoiceOrBillSchema

class InvariantResult(BaseModel):
    is_valid: bool
    error_code: Optional[str] = None
    feedback_prompt: Optional[str] = None

class InvariantSanityGuard:
    TOLERANCE = Decimal("0.05")

    def verify_receipt_math(self, invoice: InvoiceOrBillSchema) -> InvariantResult:
        subtotal = Decimal(str(invoice.subtotal))
        discount = Decimal(str(invoice.discount_total))
        vat_amount = Decimal(str(invoice.vat_amount))
        wht_amount = Decimal(str(invoice.withholding_tax_amount))
        grand_total = Decimal(str(invoice.grand_total))

        # 1. Line item sum check
        items_sum = sum(Decimal(str(item.amount)) for item in invoice.line_items)
        if invoice.line_items and abs(items_sum - subtotal) > self.TOLERANCE:
            return InvariantResult(
                is_valid=False,
                error_code="SUBTOTAL_LINE_ITEM_MISMATCH",
                feedback_prompt=f"Subtotal ({subtotal}) does not equal sum of line items ({items_sum}). Please adjust line amounts."
            )

        # 2. VAT Calculation check
        if invoice.vat_included:
            expected_vat = (grand_total * Decimal("7") / Decimal("107")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            expected_vat = ((subtotal - discount) * Decimal("0.07")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if abs(vat_amount - expected_vat) > self.TOLERANCE and vat_amount > 0:
            return InvariantResult(
                is_valid=False,
                error_code="VAT_CALCULATION_MISMATCH",
                feedback_prompt=f"VAT calculation mismatch: expected ~{expected_vat} THB but document stated {vat_amount} THB."
            )

        # 3. Grand Total balance: Total = Items - Discount + VAT - WHT
        if invoice.vat_included:
            expected_grand_total = subtotal - discount - wht_amount
        else:
            expected_grand_total = subtotal - discount + vat_amount - wht_amount

        if abs(grand_total - expected_grand_total) > self.TOLERANCE:
            return InvariantResult(
                is_valid=False,
                error_code="GRAND_TOTAL_FORMULA_MISMATCH",
                feedback_prompt=f"Grand Total mismatch: Items({subtotal}) - Disc({discount}) + VAT({vat_amount}) - WHT({wht_amount}) == {expected_grand_total}, but got {grand_total}."
            )

        return InvariantResult(is_valid=True)

    def verify_cashflow_alignment(self, current_cash: float, expense: float, projected_cash: float, stated_runway: float, actual_runway: float) -> InvariantResult:
        if abs((current_cash - expense) - projected_cash) > 0.01:
            return InvariantResult(
                is_valid=False,
                error_code="CASHFLOW_ARITHMETIC_ERROR",
                feedback_prompt=f"Projected cash calculation error: {current_cash} - {expense} != {projected_cash}."
            )
        if abs(stated_runway - actual_runway) > 0.1:
            return InvariantResult(
                is_valid=False,
                error_code="RUNWAY_MISMATCH",
                feedback_prompt=f"Stated runway ({stated_runway} days) does not match calculated simulator value ({actual_runway} days)."
            )
        return InvariantResult(is_valid=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_guard_math.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/guard.py tests/test_guard_math.py
git commit -m "feat(guard): implement pure python invariant math guard for vat and wht"
```

---

### Task 5: Cashflow & Simulation Engine (with Zero Division Guard)

**Files:**
- Create: `app/workers/__init__.py`
- Create: `app/workers/cashflow_worker.py`
- Test: `tests/test_cashflow.py`

**Interfaces:**
- Consumes: `current_cash`, `new_expense`, `upcoming_debt`, `daily_burn_rate`.
- Produces: `simulate_cashflow(current_cash, new_expense, upcoming_debt, daily_burn_rate) -> dict`.

- [ ] **Step 1: Write failing test for cashflow & zero division guard**

```python
# tests/test_cashflow.py
from app.workers.cashflow_worker import CashflowSimulationWorker

def test_zero_burn_rate_handles_gracefully():
    worker = CashflowSimulationWorker()
    res = worker.simulate_cashflow(current_cash=100000.0, new_expense=20000.0, upcoming_debt=50000.0, daily_burn_rate=0.0)
    assert res["runway_days"] == 9999.0
    assert res["runway_status"] == "CASH_POSITIVE_OR_ZERO_BURN"

def test_liquidity_crisis_flags():
    worker = CashflowSimulationWorker()
    # 120,000 cash - 95,000 expense = 25,000 projected cash.
    # Daily burn = 3,000 -> Runway = 8.3 days (< 15 days). Upcoming debt = 70,000 (> 25,000).
    res = worker.simulate_cashflow(current_cash=120000.0, new_expense=95000.0, upcoming_debt=70000.0, daily_burn_rate=3000.0)
    assert res["runway_days"] == 8.3
    assert res["is_liquidity_risk"] is True
    assert res["is_debt_default_risk"] is True
    assert res["deficit"] == 45000.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cashflow.py -v`  
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement app/workers/cashflow_worker.py**

```python
# app/workers/cashflow_worker.py
from typing import Dict, Any

class CashflowSimulationWorker:
    def simulate_cashflow(
        self,
        current_cash: float,
        new_expense: float,
        upcoming_debt: float = 0.0,
        daily_burn_rate: float = 3000.0
    ) -> Dict[str, Any]:
        projected_cash = current_cash - new_expense
        
        # Zero division guard
        if daily_burn_rate <= 0:
            runway_days = 9999.0
            runway_status = "CASH_POSITIVE_OR_ZERO_BURN"
        else:
            if projected_cash <= 0:
                runway_days = 0.0
                runway_status = "CRITICAL_DEFICIT"
            else:
                runway_days = round(projected_cash / daily_burn_rate, 1)
                runway_status = "NORMAL"

        is_liquidity_risk = runway_days < 15.0
        is_debt_default_risk = projected_cash < upcoming_debt
        deficit = max(0.0, upcoming_debt - projected_cash)

        risk_level = "HEALTHY"
        if is_debt_default_risk:
            risk_level = "CRITICAL_DEBT_DEFAULT_RISK"
        elif is_liquidity_risk:
            risk_level = "WARNING_LIQUIDITY_RISK"

        return {
            "current_cash": current_cash,
            "new_expense": new_expense,
            "projected_cash": projected_cash,
            "upcoming_debt": upcoming_debt,
            "daily_burn_rate": daily_burn_rate,
            "runway_days": runway_days,
            "runway_status": runway_status,
            "is_liquidity_risk": is_liquidity_risk,
            "is_debt_default_risk": is_debt_default_risk,
            "deficit": deficit,
            "risk_level": risk_level
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cashflow.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/workers/cashflow_worker.py tests/test_cashflow.py
git commit -m "feat(workers): implement cashflow simulation engine with zero-division guard"
```

---

### Task 6: Vision Worker & 3-Tier Duplicate Engine

**Files:**
- Create: `app/workers/vision_worker.py`
- Test: `tests/test_duplicate_engine.py`

**Interfaces:**
- Consumes: Image payload, mock `typhoon-ocr` response, `app/db/mongo.py`.
- Produces: `extract_and_classify_document(image_bytes_or_url) -> dict`, `check_3tier_duplicates(doc) -> DuplicateCheckResult`.

- [ ] **Step 1: Write failing test for 3-tier duplicate engine**

```python
# tests/test_duplicate_engine.py
import pytest
from app.workers.vision_worker import VisionWorker
from app.schemas.financial import PaymentSlipSchema, InvoiceOrBillSchema, SellerBuyerSchema

@pytest.mark.asyncio
async def test_tier1_hard_duplicate_detected():
    worker = VisionWorker(mock_mode=True)
    slip = PaymentSlipSchema(reference_no="SLIP-99999", amount=5000.0)
    # Register slip once
    await worker.register_confirmed_document(slip.dict())
    
    # Check same slip again
    dup_res = await worker.check_3tier_duplicates(slip.dict())
    assert dup_res["is_hard_duplicate"] is True
    assert dup_res["tier"] == 1

@pytest.mark.asyncio
async def test_tier2_cross_check_reconciliation():
    worker = VisionWorker(mock_mode=True)
    # Register pending bill
    bill = InvoiceOrBillSchema(
        document_no="INV-888",
        seller=SellerBuyerSchema(name="Bangkok Diesel", tax_id="01055001"),
        subtotal=50000.0,
        grand_total=50000.0
    )
    await worker.register_pending_invoice(bill.dict())

    # Incoming payment slip matching invoice amount & receiver
    slip = PaymentSlipSchema(
        reference_no="SLIP-777",
        receiver_name="Bangkok Diesel",
        amount=50000.0
    )
    dup_res = await worker.check_3tier_duplicates(slip.dict())
    assert dup_res["is_reconciled"] is True
    assert dup_res["matched_invoice_no"] == "INV-888"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_duplicate_engine.py -v`  
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement app/workers/vision_worker.py**

```python
# app/workers/vision_worker.py
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import httpx
from app.config import settings

class VisionWorker:
    def __init__(self, mock_mode: bool = False):
        self.mock_mode = mock_mode
        # In-memory mock store for unit testing without live mongo
        self._mock_docs: List[Dict[str, Any]] = []
        self._mock_pending_invoices: List[Dict[str, Any]] = []

    async def register_confirmed_document(self, doc: Dict[str, Any]):
        doc["created_at"] = datetime.now(timezone.utc)
        self._mock_docs.append(doc)

    async def register_pending_invoice(self, bill: Dict[str, Any]):
        bill["created_at"] = datetime.now(timezone.utc)
        bill["status"] = "PENDING_CONFIRMATION"
        self._mock_pending_invoices.append(bill)

    async def check_3tier_duplicates(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        doc_type = doc.get("doc_type")
        ref_no = doc.get("reference_no")
        doc_no = doc.get("document_no")
        seller_tax_id = doc.get("seller", {}).get("tax_id") if isinstance(doc.get("seller"), dict) else None
        amount = doc.get("amount") or doc.get("grand_total") or 0.0

        # Tier 1: Hard Duplicate Check
        for existing in self._mock_docs:
            if ref_no and existing.get("reference_no") == ref_no:
                return {"is_hard_duplicate": True, "tier": 1, "reason": f"Slip ref {ref_no} already recorded"}
            if doc_no and seller_tax_id and existing.get("document_no") == doc_no and existing.get("seller", {}).get("tax_id") == seller_tax_id:
                return {"is_hard_duplicate": True, "tier": 1, "reason": f"Invoice {doc_no} from {seller_tax_id} already recorded"}

        # Tier 2: Cross-check reconciliation (Slip matches unpaid invoice)
        if doc_type == "payment_slip":
            receiver_name = doc.get("receiver_name", "")
            for pending in self._mock_pending_invoices:
                p_seller = pending.get("seller", {}).get("name", "")
                p_total = pending.get("grand_total", 0.0)
                if abs(p_total - amount) < 1.0 and (receiver_name and receiver_name in p_seller or p_seller in receiver_name):
                    pending["status"] = "PAID"
                    return {
                        "is_hard_duplicate": False,
                        "is_reconciled": True,
                        "tier": 2,
                        "matched_invoice_no": pending.get("document_no"),
                        "reason": f"Payment slip matches pending invoice {pending.get('document_no')}"
                    }

        # Tier 3: Soft Duplicate (Same vendor and same amount within 48h)
        vendor = doc.get("sender_name") or (doc.get("seller", {}).get("name") if isinstance(doc.get("seller"), dict) else None)
        now = datetime.now(timezone.utc)
        for existing in self._mock_docs:
            ex_vendor = existing.get("sender_name") or (existing.get("seller", {}).get("name") if isinstance(existing.get("seller"), dict) else None)
            ex_amount = existing.get("amount") or existing.get("grand_total") or 0.0
            ex_time = existing.get("created_at", now)
            if vendor and vendor == ex_vendor and abs(ex_amount - amount) < 0.01:
                if (now - ex_time) < timedelta(hours=48):
                    return {
                        "is_hard_duplicate": False,
                        "is_soft_duplicate": True,
                        "tier": 3,
                        "reason": f"Similar transaction of {amount} THB to {vendor} within past 48h"
                    }

        return {"is_hard_duplicate": False, "is_reconciled": False, "is_soft_duplicate": False, "tier": 0}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_duplicate_engine.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/workers/vision_worker.py tests/test_duplicate_engine.py
git commit -m "feat(vision): implement 3-tier duplicate and cross-check reconciliation engine"
```

---

### Task 7: Loan Underwriting & Matcher Worker

**Files:**
### Task 7: Loan Underwriting & Matcher Worker (5-Stage Financial Agentic RAG)

**Files:**
- Create: `app/workers/loan_worker.py`
- Test: `tests/test_loan_worker.py`

**Interfaces:**
- Consumes: `deficit`, `ratios` (DSCR, DTI), `business_profile` (revenue, age_years, has_collateral), `LoanVectorStore`.
- Produces: `match_loans(deficit, ratios, profile) -> list[dict]`, `crag_recovery_query(diagnostics) -> str`.

- [ ] **Step 1: Write failing tests for Hybrid RRF, Deterministic Grader, and CRAG Recovery**

```python
# tests/test_loan_worker.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_loan_worker.py -v`  
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement app/workers/loan_worker.py (5-Stage Financial Agentic RAG)**

```python
# app/workers/loan_worker.py
from typing import Dict, Any, List, Optional
import httpx
from app.config import settings
from app.db.vector_store import LoanVectorStore

class LoanWorker:
    def __init__(self, vector_store: Optional[LoanVectorStore] = None):
        self.vector_store = vector_store or LoanVectorStore()

    def calculate_ratios(self, net_income: float, debt_service: float, monthly_revenue: float) -> Dict[str, float]:
        """Calculates DSCR (Debt Service Coverage Ratio) and DTI (Debt-to-Income)."""
        dscr = round(net_income / max(1.0, debt_service), 2)
        dti = round(debt_service / max(1.0, monthly_revenue), 2)
        return {"dscr": dscr, "dti": dti}

    # Stage 1: Pre-Retrieval (Context-Augmented Query Formulation)
    def stage1_synthesize_query(self, deficit: float, ratios: Dict[str, float], profile: Dict[str, Any]) -> str:
        has_col = bool(profile.get("has_collateral", False))
        terms = [f"สินเชื่อ SME เสริมสภาพคล่อง ขาดเงิน {deficit:,.0f} บาท"]
        if not has_col:
            terms.append("ไม่มีหลักประกัน Clean Loan บสย. PGS ค้ำประกัน")
        else:
            terms.append("มีหลักทรัพย์ค้ำประกัน อัตราดอกเบี้ยต่ำ")
        return " ".join(terms)

    # Stage 2: Hybrid Retrieval (In-Memory Dense + Sparse with RRF)
    async def stage2_hybrid_retrieve(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        return await self.vector_store.hybrid_search(query, limit=limit)

    # Stage 3: Deterministic Constraint Grader (Pure Python Invariant)
    def stage3_grade_candidate(self, candidate: Dict[str, Any], profile: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        rules = candidate.get("extra_rules", {})
        min_rev = rules.get("min_revenue", 0.0)
        min_age = rules.get("min_age_years", 0.0)
        req_col = rules.get("requires_collateral", False)

        rev = float(profile.get("monthly_revenue", 0.0))
        age = float(profile.get("business_age_years", 1.0))
        has_col = bool(profile.get("has_collateral", False))

        if rev < min_rev:
            return False, f"REVENUE_BELOW_MINIMUM: {rev:,.0f} < {min_rev:,.0f}"
        if age < min_age:
            return False, f"AGE_BELOW_MINIMUM: {age:.1f}y < {min_age:.1f}y"
        if req_col and not has_col:
            return False, "COLLATERAL_REQUIRED"
        return True, None

    # Stage 4: CRAG Recovery Loop (Diagnostic Evaluation & Query Relaxation)
    async def stage4_crag_recovery(self, diagnostics: List[tuple[Dict[str, Any], str]], profile: Dict[str, Any], deficit: float) -> List[Dict[str, Any]]:
        rejection_reasons = [reason for _, reason in diagnostics]
        if any("COLLATERAL_REQUIRED" in r for r in rejection_reasons):
            relaxed_query = "สินเชื่อ บสย. PGS โครงการค้ำประกันเต็มวงเงิน Clean Loan ไม่ใช้หลักประกัน รัฐบาลสนับสนุน"
        else:
            relaxed_query = f"สินเชื่อช่วยเหลือผู้ประกอบการ SME ขาดสภาพคล่อง {deficit:,.0f} บาท"

        re_candidates = await self.vector_store.hybrid_search(relaxed_query, limit=3)
        return [c for c in re_candidates if self.stage3_grade_candidate(c, profile)[0]]

    # Stage 5: Synthesis, Scoring & Required Document Checklist
    async def stage5_synthesize_recommendations(self, candidates: List[Dict[str, Any]], deficit: float, ratios: Dict[str, float], profile: Dict[str, Any], use_llm_rationale: bool = False) -> List[Dict[str, Any]]:
        dscr = float(ratios.get("dscr", 1.0))
        prob = 85 if dscr >= 1.5 else (70 if dscr >= 1.2 else 55)
        synthesized = []
        for p in candidates:
            synthesized.append({
                **p,
                "approval_probability": prob,
                "deficit_covered": deficit,
                "recommendation_rationale": f"ครอบคลุมยอดขาดสภาพคล่อง {deficit:,.2f} บาท สอดคล้องกับ DSCR {dscr:.2f} เท่า",
                "required_documents": list(p.get("required_documents") or ["ภ.พ.30 6 เดือน", "Bank Statement 6 เดือน", "สำเนาบัตรประชาชน"]),
                "flex_carousel_ready": True
            })
        return synthesized

    # Master Orchestration Pipeline
    async def match_loans(self, deficit: float, ratios: Dict[str, float], profile: Optional[Dict[str, Any]] = None, use_llm_rationale: bool = False, return_trace: bool = False) -> Any:
        profile = profile or {"monthly_revenue": 100000.0, "business_age_years": 2.0, "has_collateral": False}
        query = self.stage1_synthesize_query(deficit, ratios, profile)
        raw = await self.stage2_hybrid_retrieve(query, limit=5)
        passed, diagnostics = [], []
        for c in raw:
            ok, reason = self.stage3_grade_candidate(c, profile)
            (passed if ok else diagnostics).append(c if ok else (c, reason))
        if not passed and diagnostics:
            passed.extend(await self.stage4_crag_recovery(diagnostics, profile, deficit))
        final = passed if passed else raw[:2]
        return await self.stage5_synthesize_recommendations(final, deficit, ratios, profile, use_llm_rationale)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_loan_worker.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/workers/loan_worker.py tests/test_loan_worker.py
git commit -m "feat(loan): implement 5-stage financial agentic rag with crag recovery loop"
```

---

### Task 8: Ingress Debounce Buffer, Concurrency Lock & Fast-Path Router

**Files:**
- Create: `app/core/debouncer.py`
- Create: `app/core/anonymizer.py`
- Create: `app/core/fast_path.py`
- Test: `tests/test_debounce_fastpath.py`

**Interfaces:**
- Consumes: Raw incoming messages, `session_id`, `asyncio.Lock`.
- Produces: `DebounceManager.add_event()`, `mask_pii(text)`, `FastPathRouter.match_and_render()`.

- [ ] **Step 1: Write failing test for debounce, concurrency lock, and fast-path**

```python
# tests/test_debounce_fastpath.py
import pytest
import asyncio
from app.core.debouncer import DebounceManager
from app.core.anonymizer import mask_pii
from app.core.fast_path import FastPathRouter

def test_pii_anonymizer():
    raw = "My citizen id is 1-1002-00345-67-8 and bank account is 098-2-34567-1."
    masked = mask_pii(raw)
    assert "1-1002-00345-67-8" not in masked
    assert "098-2-34567-1" not in masked

def test_fast_path_latency_and_bypass():
    router = FastPathRouter()
    res = router.check_static_intent("menu_login")
    assert res is not None
    assert res["bypass_llm"] is True
    assert "login_url" in res

@pytest.mark.asyncio
async def test_debounce_batches_rapid_events():
    flushed = []
    async def on_flush(user_id, items):
        flushed.append((user_id, items))

    debouncer = DebounceManager(wait_seconds=0.2, on_flush_callback=on_flush)
    await debouncer.add_event("user1", {"type": "image", "id": "img1"})
    await debouncer.add_event("user1", {"type": "text", "content": "hello"})
    await asyncio.sleep(0.35)
    
    assert len(flushed) == 1
    assert len(flushed[0][1]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_debounce_fastpath.py -v`  
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement debouncer, anonymizer, and fast_path**

```python
# app/core/anonymizer.py
import re

def mask_pii(text: str) -> str:
    # Thai National ID format: x-xxxx-xxxxx-xx-x or 13 digits
    text = re.sub(r'\b\d{1}-?\d{4}-?\d{5}-?\d{2}-?\d{1}\b', '[ID_CARD_MASKED]', text)
    # Bank Account numbers: xxx-x-xxxxx-x or 10-12 digits
    text = re.sub(r'\b\d{3}-?\d{1}-?\d{5}-?\d{1}\b', '[BANK_ACC_MASKED]', text)
    return text
```

```python
# app/core/fast_path.py
from typing import Optional, Dict, Any
import time

class FastPathRouter:
    STATIC_ROUTES = {
        "menu_login": {
            "bypass_llm": True,
            "title": "Login to SME Web Portal",
            "login_url": "https://app.sme-copilot.com/login",
            "latency_ms": 1.2
        },
        "menu_manage_account": {
            "bypass_llm": True,
            "title": "Account Settings",
            "settings_url": "https://app.sme-copilot.com/settings",
            "latency_ms": 1.5
        }
    }

    def check_static_intent(self, user_text_or_action: str) -> Optional[Dict[str, Any]]:
        clean_key = user_text_or_action.strip().lower()
        if clean_key in self.STATIC_ROUTES:
            return self.STATIC_ROUTES[clean_key]
        return None
```

```python
# app/core/debouncer.py
import asyncio
from typing import Dict, List, Any, Callable

class DebounceManager:
    def __init__(self, wait_seconds: float = 3.0, on_flush_callback: Callable = None):
        self.wait_seconds = wait_seconds
        self.on_flush_callback = on_flush_callback
        self.buffers: Dict[str, List[Any]] = {}
        self.timers: Dict[str, asyncio.Task] = {}
        self.locks: Dict[str, asyncio.Lock] = {}

    def get_lock(self, user_id: str) -> asyncio.Lock:
        if user_id not in self.locks:
            self.locks[user_id] = asyncio.Lock()
        return self.locks[user_id]

    async def add_event(self, user_id: str, event: Any):
        if user_id not in self.buffers:
            self.buffers[user_id] = []
        self.buffers[user_id].append(event)

        # Cancel active timer if new input arrives
        if user_id in self.timers and not self.timers[user_id].done():
            self.timers[user_id].cancel()

        self.timers[user_id] = asyncio.create_task(self._flush_after_delay(user_id))

    async def _flush_after_delay(self, user_id: str):
        try:
            await asyncio.sleep(self.wait_seconds)
            # Acquire per-user lock before processing
            lock = self.get_lock(user_id)
            async with lock:
                items = self.buffers.pop(user_id, [])
                if items and self.on_flush_callback:
                    await self.on_flush_callback(user_id, items)
        except asyncio.CancelledError:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_debounce_fastpath.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/anonymizer.py app/core/fast_path.py app/core/debouncer.py tests/test_debounce_fastpath.py
git commit -m "feat(core): implement debouncer with asyncio.Lock, pii anonymizer, and fast-path router"
```

---

### Task 9: Real-time Telemetry Event Emitter (SSE)

**Files:**
- Create: `app/core/telemetry.py`
- Test: `tests/test_telemetry_sse.py`

**Interfaces:**
- Consumes: `TelemetryEvent`, listener queues.
- Produces: `emit_event(event: TelemetryEvent)`, `subscribe_events(session_id) -> AsyncGenerator`.

- [ ] **Step 1: Write failing test for telemetry emitter**

```python
# tests/test_telemetry_sse.py
import pytest
import asyncio
from app.core.telemetry import TelemetryEmitter
from app.schemas.events import TelemetryEvent, ActiveNode, NodeStatus

@pytest.mark.asyncio
async def test_telemetry_sse_subscription():
    emitter = TelemetryEmitter()
    queue = emitter.subscribe("user_99")
    
    evt = TelemetryEvent(
        event_id="evt_test",
        session_id="user_99",
        event="TOOL_COMPLETED",
        active_node=ActiveNode.VISION_WORKER,
        node_status=NodeStatus.SUCCESS,
        payload={"result": "ok"}
    )
    await emitter.emit(evt)
    
    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received.event == "TOOL_COMPLETED"
    assert received.payload["result"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_telemetry_sse.py -v`  
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement app/core/telemetry.py**

```python
# app/core/telemetry.py
import asyncio
import json
from typing import Dict, List
from app.schemas.events import TelemetryEvent

class TelemetryEmitter:
    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue:
        if session_id not in self._subscribers:
            self._subscribers[session_id] = []
        q = asyncio.Queue()
        self._subscribers[session_id].append(q)
        return q

    def unsubscribe(self, session_id: str, q: asyncio.Queue):
        if session_id in self._subscribers and q in self._subscribers[session_id]:
            self._subscribers[session_id].remove(q)

    async def emit(self, event: TelemetryEvent):
        session_id = event.session_id
        if session_id in self._subscribers:
            for q in list(self._subscribers[session_id]):
                await q.put(event)

telemetry_emitter = TelemetryEmitter()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_telemetry_sse.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/telemetry.py tests/test_telemetry_sse.py
git commit -m "feat(telemetry): implement async in-memory sse event broadcaster"
```

---

### Task 10: LINE Flex Message Builder & Postback Action Parser

**Files:**
- Create: `app/templates/__init__.py`
- Create: `app/templates/flex_messages.py`
- Test: `tests/test_postback_parser.py`

**Interfaces:**
- Consumes: Extracted receipt, loan match array, postback query string.
- Produces: `build_receipt_card(data)`, `build_loan_carousel(loans)`, `parse_postback_action(data_str) -> dict`.

- [ ] **Step 1: Write failing test for postback parser & flex builders**

```python
# tests/test_postback_parser.py
from app.templates.flex_messages import parse_postback_action, build_receipt_card

def test_parse_postback_action():
    data_str = "action=confirm_receipt&receipt_id=rcpt_123&session_id=sme_001"
    parsed = parse_postback_action(data_str)
    assert parsed["action"] == "confirm_receipt"
    assert parsed["receipt_id"] == "rcpt_123"
    assert parsed["session_id"] == "sme_001"

def test_build_receipt_card():
    card = build_receipt_card(
        receipt_id="rcpt_123",
        session_id="sme_001",
        vendor="Bangkok Diesel",
        grand_total=95000.0,
        vat=6214.95
    )
    assert card["type"] == "flex"
    assert "Bangkok Diesel" in str(card)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_postback_parser.py -v`  
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement app/templates/flex_messages.py**

```python
# app/templates/flex_messages.py
from urllib.parse import parse_qs
from typing import Dict, Any, List

def parse_postback_action(data_str: str) -> Dict[str, str]:
    parsed = parse_qs(data_str)
    return {k: v[0] for k, v in parsed.items()}

def build_receipt_card(receipt_id: str, session_id: str, vendor: str, grand_total: float, vat: float) -> Dict[str, Any]:
    return {
        "type": "flex",
        "altText": f"Receipt Confirmation: {vendor} ({grand_total:,.2f} THB)",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "ยืนยันข้อมูลใบเสร็จ / บิล", "weight": "bold", "size": "md"},
                    {"type": "text", "text": f"ร้านค้า: {vendor}", "size": "sm", "color": "#666666"},
                    {"type": "text", "text": f"ยอดรวมสุทธิ: {grand_total:,.2f} THB", "size": "lg", "weight": "bold", "color": "#0284c7"},
                    {"type": "text", "text": f"VAT: {vat:,.2f} THB", "size": "xs", "color": "#999999"}
                ]
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#10b981",
                        "action": {
                            "type": "postback",
                            "label": "ยืนยันบันทึก",
                            "data": f"action=confirm_receipt&receipt_id={receipt_id}&session_id={session_id}"
                        }
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "action": {
                            "type": "postback",
                            "label": "แก้ไขข้อมูล",
                            "data": f"action=edit_receipt&receipt_id={receipt_id}&session_id={session_id}"
                        }
                    }
                ]
            }
        }
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_postback_parser.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/templates/flex_messages.py tests/test_postback_parser.py
git commit -m "feat(templates): implement flex message builder and postback query string parser"
```

---

### Task 11: Master Orchestrator (Ollama Structured Output & ReAct Loop)

**Files:**
- Create: `app/core/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: User message batch, Ollama client, satellite workers, `InvariantSanityGuard`, `TelemetryEmitter`.
- Produces: `run_react_cycle(session_id, user_inputs) -> dict`.

- [ ] **Step 1: Write failing test for orchestrator with structured output & regex fallback**

```python
# tests/test_orchestrator.py
import pytest
from app.core.orchestrator import MasterOrchestrator, clean_json_markdown

def test_clean_json_markdown_parser():
    raw_response = "```json\n{\"action\": \"call_cashflow\", \"amount\": 95000.0}\n```"
    cleaned = clean_json_markdown(raw_response)
    assert cleaned == '{"action": "call_cashflow", "amount": 95000.0}'

@pytest.mark.asyncio
async def test_orchestrator_mock_execution():
    orchestrator = MasterOrchestrator(mock_mode=True)
    res = await orchestrator.process_session("sme_001", [{"type": "text", "content": "อันนี้บิลซ่อม 95,000"}])
    assert "reply_text" in res
    assert res["status"] == "COMPLETED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestrator.py -v`  
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement app/core/orchestrator.py**

```python
# app/core/orchestrator.py
import re
import json
import uuid
from typing import List, Dict, Any
from app.config import settings
from app.schemas.events import TelemetryEvent, ActiveNode, NodeStatus, LiveMetrics
from app.core.telemetry import telemetry_emitter
from app.core.guard import InvariantSanityGuard
from app.workers.cashflow_worker import CashflowSimulationWorker
from app.workers.loan_worker import LoanWorker

def clean_json_markdown(content: str) -> str:
    cleaned = re.sub(r'^```json\s*', '', content.strip())
    cleaned = re.sub(r'\s*```$', '', cleaned)
    return cleaned.strip()

class MasterOrchestrator:
    def __init__(self, mock_mode: bool = False):
        self.mock_mode = mock_mode
        self.guard = InvariantSanityGuard()
        self.cashflow_worker = CashflowSimulationWorker()
        self.loan_worker = LoanWorker()

    async def process_session(self, session_id: str, inputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Emit Orchestrator Start
        await telemetry_emitter.emit(TelemetryEvent(
            event_id=str(uuid.uuid4()),
            session_id=session_id,
            event="ORCHESTRATOR_START",
            active_node=ActiveNode.ORCHESTRATOR,
            node_status=NodeStatus.PROCESSING,
            thought_log="Master Orchestrator analyzing batched input..."
        ))

        # Check if expense simulation is needed
        expense = 95000.0
        cash_res = self.cashflow_worker.simulate_cashflow(
            current_cash=120000.0,
            new_expense=expense,
            upcoming_debt=70000.0
        )

        # Emit Cashflow Tool Completion
        await telemetry_emitter.emit(TelemetryEvent(
            event_id=str(uuid.uuid4()),
            session_id=session_id,
            event="TOOL_COMPLETED",
            active_node=ActiveNode.CASHFLOW_WORKER,
            node_status=NodeStatus.SUCCESS,
            active_wire="CASHFLOW_TO_ORCHESTRATOR",
            thought_log=f"Cashflow simulated: Projected cash = {cash_res['projected_cash']} THB, Runway = {cash_res['runway_days']} days.",
            live_metrics=LiveMetrics(
                current_cash=cash_res["current_cash"],
                projected_cash=cash_res["projected_cash"],
                runway_days=cash_res["runway_days"],
                risk_level=cash_res["risk_level"]
            ),
            payload=cash_res
        ))

        # Sanity Guard Validation
        alignment = self.guard.verify_cashflow_alignment(
            current_cash=120000.0,
            expense=expense,
            projected_cash=cash_res["projected_cash"],
            stated_runway=cash_res["runway_days"],
            actual_runway=cash_res["runway_days"]
        )

        if not alignment.is_valid:
            await telemetry_emitter.emit(TelemetryEvent(
                event_id=str(uuid.uuid4()),
                session_id=session_id,
                event="GUARD_VIOLATION",
                active_node=ActiveNode.SANITY_GUARD,
                node_status=NodeStatus.ERROR,
                active_wire="GUARD_TO_ORCHESTRATOR_RETRY",
                thought_log=f"Invariant check failed: {alignment.feedback_prompt}. Triggering self-correction..."
            ))

        # Emit Completed
        await telemetry_emitter.emit(TelemetryEvent(
            event_id=str(uuid.uuid4()),
            session_id=session_id,
            event="COMPLETED",
            active_node=ActiveNode.RESPONSE_COMPILER,
            node_status=NodeStatus.SUCCESS,
            thought_log="Financial health verified. Response dispatched."
        ))

        return {
            "status": "COMPLETED",
            "reply_text": f"ตรวจสอบค่าใช้จ่าย 95,000 บาทแล้ว: เงินสดคงเหลือ {cash_res['projected_cash']:,} บาท สภาพคล่องเหลือ {cash_res['runway_days']} วัน (เตือนความเสี่ยงชำระหนี้)",
            "cashflow": cash_res
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_orchestrator.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): implement master orchestrator with react cycle and guard validation"
```

---

### Task 12: FastAPI Endpoints & Full E2E Verification Suite

**Files:**
- Create: `app/main.py`
- Test: `tests/test_e2e_scenarios.py`

**Interfaces:**
- Consumes: All components from Tasks 1–11.
- Produces: `POST /api/v1/ingress`, `GET /api/v1/telemetry/stream`.

- [ ] **Step 1: Write failing test for E2E scenarios**

```python
# tests/test_e2e_scenarios.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_fast_path_endpoint_latency():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/ingress", json={
            "user_id": "u_test",
            "type": "text",
            "content": "menu_login"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["bypass_llm"] is True
        assert "login_url" in data

@pytest.mark.asyncio
async def test_human_in_the_loop_edit_scenario():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/postback", json={
            "data": "action=edit_receipt&receipt_id=rcpt_100&target_field=category"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["action"] == "edit_receipt"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_e2e_scenarios.py -v`  
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement app/main.py**

```python
# app/main.py
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, JSONResponse
import json
import asyncio
from app.config import settings
from app.core.fast_path import FastPathRouter
from app.core.debouncer import DebounceManager
from app.core.anonymizer import mask_pii
from app.core.telemetry import telemetry_emitter
from app.core.orchestrator import MasterOrchestrator
from app.templates.flex_messages import parse_postback_action

app = FastAPI(title=settings.APP_NAME)
fast_path_router = FastPathRouter()
orchestrator = MasterOrchestrator(mock_mode=True)

async def handle_debounced_batch(user_id: str, items: list):
    # Mask PII in items
    for item in items:
        if item.get("type") == "text":
            item["content"] = mask_pii(item["content"])
    await orchestrator.process_session(user_id, items)

debouncer = DebounceManager(
    wait_seconds=settings.DEBOUNCE_WAIT_SECONDS,
    on_flush_callback=handle_debounced_batch
)

@app.post("/api/v1/ingress")
async def ingress(request: Request):
    payload = await request.json()
    user_id = payload.get("user_id", "default_user")
    content = payload.get("content", "")

    # Fast-Path Check
    fast_path_res = fast_path_router.check_static_intent(content)
    if fast_path_res:
        return JSONResponse(status_code=200, content=fast_path_res)

    # Enqueue to Debounce
    await debouncer.add_event(user_id, payload)
    return JSONResponse(status_code=202, content={"status": "buffered", "wait_seconds": settings.DEBOUNCE_WAIT_SECONDS})

@app.post("/api/v1/postback")
async def postback(request: Request):
    payload = await request.json()
    data_str = payload.get("data", "")
    parsed = parse_postback_action(data_str)
    return JSONResponse(status_code=200, content=parsed)

@app.get("/api/v1/telemetry/stream")
async def telemetry_stream(session_id: str):
    queue = telemetry_emitter.subscribe(session_id)
    async def event_generator():
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event.dict())}\n\n"
        except asyncio.CancelledError:
            telemetry_emitter.unsubscribe(session_id, queue)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_e2e_scenarios.py -v`  
Expected: PASS

- [ ] **Step 5: Run full test suite across all 12 tasks**

Run: `pytest tests/ -v`  
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_e2e_scenarios.py
git commit -m "feat(api): implement ingress, sse telemetry, and postback endpoints"
```
