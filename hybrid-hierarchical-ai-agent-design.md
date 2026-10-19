# Design Specification: Hybrid Hierarchical AI Agent for SME Financial Copilot

**Date:** 2026-10-17  
**Status:** Approved  
**Author:** Antigravity & Project Leader  

---

## 1. Executive Summary & Objective

This project builds the backend AI subsystem for an SME Financial Copilot. The system features a **Hybrid Hierarchical AI Agent Architecture** designed to assist Thai SMEs in managing cash flow, analyzing financial documents, predicting liquidity runway, and recommending credit/loan solutions with 100% mathematical precision and zero hallucinations.

The AI subsystem operates decoupled from the web frontend, delivering real-time telemetry events via Server-Sent Events (SSE) and HTTP Webhooks to the fullstack web application and sending interactive Flex Messages to LINE users.

---

## 2. Technology Stack & Runtime Configuration

- **Language & Core Framework:** Python 3.11+, FastAPI (Async REST & SSE streaming), Pydantic v2
- **Orchestrator LLM:** Local **Ollama** running `Qwen3-1.7B` (or `Qwen2.5-Coder/Instruct`) via OpenAI-compatible API (`http://localhost:11434/v1`)
  - **Structured Output Enforcement:** Uses Ollama structured output mode (`format=PydanticModel.model_json_schema()`) and defensive JSON regex parsing in `orchestrator.py` to prevent formatting failures common in smaller parameter models.
- **Document OCR:** **OpenTyphoon OCR API** (`typhoon-ocr`) for Thai/English receipt and statement text extraction
- **Database & Persistence:** **MongoDB** (Async Motor client) with centralized connection pooling
- **Vector Search / RAG:** `MongoDBAtlasVectorSearch` on loan criteria & bank policies
- **Deterministic Engine:** 100% Pure Python rule-based algorithms for cash flow simulation, 3-tier duplicate checking, and mathematical invariant guardrails

---

## 3. Directory Structure

```text
fintech/
├── app/
│   ├── main.py                     # FastAPI application, route registration, lifecycle
│   ├── config.py                   # Environment settings (Ollama URL, Typhoon API Key, Mongo URI)
│   ├── db/                         # Centralized database pool & vector search
│   │   ├── __init__.py
│   │   ├── mongo.py                # Async Motor MongoDB connection pool & collection access
│   │   └── vector_store.py         # MongoDBAtlasVectorSearch instance for loan policy RAG
│   ├── core/                       # Core engine components
│   │   ├── __init__.py
│   │   ├── debouncer.py            # Debounce Buffer (3-5s window) & Per-User asyncio.Lock
│   │   ├── anonymizer.py           # Fast PII regex masking (Thai National ID, Bank accounts)
│   │   ├── fast_path.py            # Static Intent Router (Rich Menu Links, Cache Renders < 200ms)
│   │   ├── orchestrator.py         # Master ReAct Agent (Ollama client, CoT Scratchpad, JSON fallback)
│   │   ├── guard.py                # Reflection & Invariant Sanity Guard (Math & Policy checks)
│   │   └── telemetry.py            # SSE / Webhook Event Emitter (real-time telemetry)
│   ├── workers/                    # Satellite Nodes (Decoupled workers)
│   │   ├── __init__.py
│   │   ├── vision_worker.py        # typhoon-ocr API + 3 doc types + 3-tier duplicate engine
│   │   ├── cashflow_worker.py      # Pure Python Math (Burn Rate, Runway, Zero-division guard)
│   │   └── loan_worker.py          # DSCR/DTI ratios + Atlas Vector Search + Qwen RAG
│   ├── schemas/                    # Pydantic Schemas / Contracts
│   │   ├── __init__.py
│   │   ├── state.py                # Global Agent State & Conversation Context
│   │   ├── events.py               # Telemetry Event Models (SSE payload for fullstack web)
│   │   └── financial.py            # PaymentSlip, InvoiceOrBill, BankStatement models
│   └── templates/                  # Response rendering
│       ├── __init__.py
│       └── flex_messages.py        # LINE Flex Message JSON Builders & Postback schemas
├── tests/                          # Automated Unit & Integration Tests
│   ├── __init__.py
│   ├── test_guard_math.py          # Invariant sanity checks (VAT inclusive/exclusive, WHT)
│   ├── test_cashflow.py            # Runway math & zero division guard
│   ├── test_duplicate_engine.py    # Tier 1, Tier 2 cross-check, Tier 3 soft duplicate
│   ├── test_debounce_fastpath.py   # Debounce queue & fast-path latency (< 200ms)
│   ├── test_postback_parser.py     # Postback query string parsing & state binding
│   └── test_telemetry_sse.py       # SSE payload and event order verification
└── docs/superpowers/specs/
    └── 2026-10-17-hybrid-hierarchical-ai-agent-design.md
```

---

## 4. End-to-End Data Flow Lifecycle

```
[ LINE Messaging API / User Input ]
               │
               ▼
[ POST /api/v1/ingress ]
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. INGRESS BUFFER, PER-USER LOCK & PII MASKING              │
├─────────────────────────────────────────────────────────────┤
│ • Per-User Concurrency Lock (asyncio.Lock per session_id)   │
│ • Debounce Window Buffer (3-5s: batch rapid text + photos)  │
│ • Fast PII Anonymizer (Regex mask Thai National ID & Acc)   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                [ Is Static Rich Menu / Link? ]
                               │
            ┌──────────────────┴──────────────────┐
        [ YES ]                                [ NO ]
            │                                     │
            ▼                                     ▼
┌───────────────────────────┐ ┌───────────────────────────────────────┐
│ FAST-PATH RENDERER        │ │ 2. MASTER ORCHESTRATOR (Qwen in Ollama)│
│ (Latency < 200ms)         │ ├───────────────────────────────────────┤
│ • Direct Cached Flex/Link │ │ • Load Context & Statement Memory     │
│ • Bypass LLM entirely     │ │ • Scratchpad Goal & Reasoning Cycle   │
└───────────┬───────────────┘ └───────────────────┬───────────────────┘
            │                                     │
            │                  [ Select Satellite Worker Node ]
            │                                     │
            │         ┌───────────────────────────┼───────────────────────────┐
            │         ▼                           ▼                           ▼
            │ ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐
            │ │ SATELLITE NODE 1:     │ │ SATELLITE NODE 2:     │ │ SATELLITE NODE 3:     │
            │ │ Vision & Audit Worker │ │ Cashflow & Simulation │ │ Loan Matcher Worker   │
            │ ├───────────────────────┤ ├───────────────────────┤ ├───────────────────────┤
            │ │ • typhoon-ocr API     │ │ • Daily Burn Rate     │ │ • DSCR & DTI Ratios   │
            │ │ • 3-Doc Classification│ │ • What-If Simulation  │ │ • Atlas Vector Search │
            │ │ • 3-Tier Duplication  │ │ • Zero Division Guard │ │ • Bank Match & Scoring│
            │ └───────────┬───────────┘ └───────────┬───────────┘ └───────────┬───────────┘
            │             │                       │                       │
            │             └───────────────────────┼───────────────────────┘
            │                                     │
            │                                     ▼
            │                         ┌───────────────────────┐
            │                         │ SSE Telemetry Emitter │ ──► [ Fullstack Dashboard ]
            │                         │ (State, Node & Payload│     (Real-time Wire & Node)
            │                         └───────────┬───────────┘
            │                                     │
            │                                     ▼
            │                     [ Task Finished & Draft Ready? ]
            │                                     │
            │            ┌────────────────────────┴────────────────────────┐
            │        [ NO ] (Needs More Steps)                         [ YES ]
            │            │                                                 │
            │            └───────────────┐                                 ▼
            │                            │             ┌───────────────────────────────────────┐
            │                            │             │ 3. HYBRID REFLECTION & SANITY GUARD   │
            │                            │             ├───────────────────────────────────────┤
            │                            │             │ • Math Check: VAT (Inc/Exc) + WHT     │
            │                            │             │ • Cash Balance & Runway Alignment     │
            │                            │             │ • Policy Validation (Crisis Warning)  │
            │                            │             └───────────────────┬───────────────────┘
            │                            │                                 │
            │                            │                      [ Sanity Check Passed? ]
            │                            │                                 │
            │                            │                  ┌──────────────┴──────────────┐
            │                            │              [ FAIL ]                       [ PASS ]
            │                            │                  │                             │
            │                            │                  ▼                             ▼
            │                            │          [ SSE: GUARD_VIOLATION ]  ┌───────────────────────┐
            │                            └──────────[ Loop Back 1/2 ]         │ 4. MULTI-MODAL OUTPUT │
            │                                                                 ├───────────────────────┤
            │                                                                 │ • Compile LINE Flex   │
            │                                                                 │ • Emit SSE COMPLETED  │
            │                                                                 │ • Persist DB State    │
            │                                                                 └───────────┬───────────┘
            │                                                                             │
            └─────────────────────────────────────────────────────────────────────────────┘
                                                │
                                                ▼
                                   [ DISPATCH TO LINE CLIENT ]
```

---

## 5. Detailed Component Specifications

### 5.1 Satellite Worker 1: Vision & Document Intelligence (`workers/vision_worker.py`)
- **Technology:** AI (`typhoon-ocr` API) + Rule-based verification.
- **Classification:** Categorizes image into 3 document types defined in `receipt_template/`:
  1. `payment_slip`: `reference_no`, `transaction_datetime`, `amount`, `sender_name`, `sender_account_masked`, `receiver_name`, `receiver_account_masked`, `memo`, `status_text`.
  2. `invoice_or_bill`: `document_no`, `issue_date`, `due_date`, `credit_term_days`, `seller` (`name`, `tax_id`), `buyer` (`name`, `tax_id`), `line_items` (`description`, `quantity`, `unit_price`, `amount`), `subtotal`, `discount_total`, `vat_included`, `vat_amount`, `withholding_tax_amount`, `grand_total`.
  3. `bank_statement`: `account` (`bank`, `account_holder`, `account_masked`, `period_start`, `period_end`, `balance_forward`, `closing_balance`), `transactions` (`date`, `code`, `channel`, `description`, `withdrawal`, `deposit`, `amount`, `balance`, `reference_code`).
  - *Non-financial:* Returns `non_financial_image` for standard conversational handling.
- **3-Tier Duplicate & Reconciliation Engine:**
  - **Tier 1 (Hard Duplicate):** Checks `reference_no` (slips) or `(seller.tax_id, document_no)` (invoices) in MongoDB `receipts` collection. Rejects immediate duplicates.
  - **Tier 2 (Cross-Check Reconciliation):** When a `payment_slip` arrives, queries unpaid `invoice_or_bill` records with matching amount and vendor, marking them as `PAID`.
  - **Tier 3 (Soft Duplicate):** Checks if the same vendor and same amount occurred within 48 hours. If found, sets `is_soft_duplicate: True` to prompt user confirmation.

### 5.2 Satellite Worker 2: Cashflow & Simulation (`workers/cashflow_worker.py`)
- **Technology:** 100% Deterministic Python math.
- **Formulas & Zero Division Guard:**
  $$\text{Daily Burn Rate} = \frac{\sum \text{Expenses in 30 Days}}{30}$$
  $$\text{Projected Cash} = \text{Current Cash} - \text{New Expense}$$
  - **Zero Division Guard:**
    ```python
    if daily_burn_rate <= 0:
        runway_days = 9999.0
        runway_status = "CASH_POSITIVE_OR_ZERO_BURN"
    else:
        runway_days = round(projected_cash / daily_burn_rate, 1)
    ```
  - If $\text{Projected Cash} \le 0$, sets `runway_days = 0.0` and `risk_level = "CRITICAL_DEFICIT"`.
- **Alert Triggers:**
  - `WARNING_LIQUIDITY_RISK`: when `runway_days < 15.0`
  - `CRITICAL_DEBT_DEFAULT_RISK`: when `projected_cash < upcoming_debt_due`

### 5.3 Satellite Worker 3: Loan Underwriter & Matcher (5-Stage Financial Agentic RAG)
- **Technology:** 5-Stage Financial Agentic RAG (In-Memory Dense FAISS + Sparse BM25 + Reciprocal Rank Fusion + Deterministic Grader + CRAG Recovery Loop + Qwen Rationale).
- **Ratios:**
  $$\text{DSCR} = \frac{\text{Net Operating Income}}{\text{Total Debt Service}}$$
  $$\text{DTI} = \frac{\text{Monthly Debt}}{\text{Monthly Revenue}}$$
- **5-Stage Pipeline Architecture:**
  1. **Stage 1: Pre-Retrieval (Query Synthesis):** Context-augmented query formulation using `deficit`, `dscr`, `business_age_years`, and `has_collateral`.
  2. **Stage 2: Hybrid Retrieval (FAISS + BM25 with RRF):** In-memory Dense (FAISS) for semantic context + Sparse (BM25) for exact financial terms ("OD", "บสย.", "Factoring", "Clean Loan"), fused via Reciprocal Rank Fusion (RRF).
  3. **Stage 3: Deterministic Constraint Grader:** Pure Python assertion layer checking candidates against `extra_rules` (`min_revenue`, `min_age`, `requires_collateral`).
  4. **Stage 4: Corrective RAG (CRAG) Recovery Loop:** If candidate fails due to constraints (e.g. `COLLATERAL_REQUIRED`), diagnoses reason, relaxes query (e.g. Clean Loan / บสย. guarantee), and re-retrieves (max 1 retry loop).
  5. **Stage 5: Synthesis & Document Checklist:** Computes approval probability score (%), synthesizes pros/cons using Qwen, and generates a concrete `required_documents` checklist (e.g. ภ.พ.30, สเตทเมนต์ 6 เดือน, หนังสือรับรองบริษัท) formatted for LINE Carousel.

### 5.4 Reflection & Invariant Sanity Guard (`core/guard.py`)
- **Technology:** 100% Pure Python assertions.
- **Math Invariants:**
  1. Quantity multiplication: $\text{quantity} \times \text{unit\_price} == \text{amount}$
  2. VAT Exclusive (`vat_included: False`): $\text{vat\_amount} \approx \text{subtotal} \times 0.07 \ (\pm 0.05 \text{ THB})$
  3. VAT Inclusive (`vat_included: True`): $\text{vat\_amount} \approx \text{grand\_total} \times \frac{7}{107} \ (\pm 0.05 \text{ THB})$
  4. Grand Total with Withholding Tax (WHT):
     $$\text{grand\_total} == \sum(\text{line\_items.amount}) - \text{discount\_total} + \text{vat\_amount} - \text{withholding\_tax\_amount}$$
  5. Cashflow Alignment: Output numbers must match `cashflow_worker.py` results exactly.
- **Policy Enforcement:**
  - `runway_days < 15` requires warning and financing recommendation.
  - `needs_human_review == True` requires prompting user about unreadable fields.
- **Telemetry Hook on Violation:**
  When validation fails, emits `GUARD_VIOLATION` event via SSE to light up the glowing retry wire on the dashboard, feeds error back to Orchestrator (max 2 retries, then safe fallback).

### 5.5 State Concurrency & Model Enforcement Guardrails
- **Ollama Output Enforcement:**
  - Utilize Ollama's structured output mode (`format=PydanticModel.model_json_schema()`) to ensure deterministic JSON arguments during worker dispatch.
  - Implement a defensive JSON regex extraction fallback in `orchestrator.py` to handle stray markdown fences (````json ... ````).
- **Session Concurrency Lock:**
  - Enforce an in-memory `asyncio.Lock` per `session_id` inside `core/debouncer.py` to serialize concurrent requests and prevent state corruption during rapid postback taps or overlapping photo/text uploads.
- **Temporary Document Lifecycle:**
  - Receipts awaiting user confirmation are persisted in MongoDB with `status: "PENDING_CONFIRMATION"`.
  - Configured with a MongoDB TTL index (`expireAfterSeconds: 86400`) to automatically purge abandoned pending receipts after 24 hours.

---

## 6. Contracts & Schemas

### 6.1 Telemetry Event Schema (`schemas/events.py`)
```json
{
  "event_id": "evt_98a7b6c5",
  "timestamp": "2026-10-17T12:55:00.123Z",
  "session_id": "sme_user_001",
  "event": "TOOL_COMPLETED",
  "active_node": "VISION_WORKER",
  "node_status": "SUCCESS",
  "active_wire": "VISION_TO_ORCHESTRATOR",
  "thought_log": "Extracted invoice data successfully. No duplicate detected.",
  "live_metrics": {
    "latency_ms": 450,
    "current_cash": 120000.0,
    "projected_cash": 25000.0,
    "runway_days": 11.5,
    "risk_level": "WARNING_LIQUIDITY_RISK"
  },
  "payload": {
    "doc_type": "invoice_or_bill",
    "document_no": "INV-2026-0089",
    "seller_name": "Bangkok Diesel Maintenance Ltd.",
    "grand_total": 95000.0,
    "vat_amount": 6214.95,
    "vat_included": true,
    "withholding_tax_amount": 0.0,
    "line_items": [
      { "description": "Truck Engine Overhaul", "quantity": 1, "unit_price": 95000.0, "amount": 95000.0 }
    ]
  }
}
```

### 6.2 LINE Postback Standards (`templates/flex_messages.py`)
Every interactive button transmits a deterministic query-string payload:
- **Confirm Receipt:** `action=confirm_receipt&receipt_id=<ID>&session_id=<USER_ID>`
- **Edit Receipt:** `action=edit_receipt&receipt_id=<ID>&target_field=<FIELD>`
- **Explore Loan:** `action=match_loan&deficit_amount=<AMOUNT>&risk_level=<RISK>`

### 6.3 Receipt Document Lifecycle States in MongoDB
In the `receipts` MongoDB collection:
- `status`: `"PENDING_CONFIRMATION" | "CONFIRMED" | "DISCARDED"`
- **Index:** `create_index("created_at", expireAfterSeconds=86400, partialFilterExpression={"status": "PENDING_CONFIRMATION"})` to automatically discard unconfirmed temporary receipts after 24 hours.

---

## 7. Verification & Testing Plan

1. **Unit Tests:**
   - `test_guard_math.py`: VAT Inclusive ($7/107$), VAT Exclusive ($7\%$), WHT subtraction.
   - `test_cashflow.py`: Zero division guard, negative cash, runway threshold triggers.
   - `test_duplicate_engine.py`: Tier 1 hard duplicate, Tier 2 cross-check reconciliation, Tier 3 48-hour soft duplicate.
   - `test_debounce_fastpath.py`: Buffer window flushing, `asyncio.Lock` session serialization, and fast-path bypass latency (< 200ms).
   - `test_postback_parser.py`: Query string parsing and transaction state binding.
2. **Integration Tests:**
   - Mocked Ollama & `typhoon-ocr` ReAct tool calling with structured output enforcement & JSON fallback regex parser.
   - Self-correction loop validation on injected math discrepancies.
   - SSE telemetry stream order and payload verification.
3. **E2E Showcase Scenarios:**
   - Scenario 1: Critical liquidity expense triggering loan recommendations.
   - Scenario 2: Cross-check reconciliation of payment slip against unpaid invoice.
   - Scenario 3: Human-in-the-loop multi-turn edit on receipt category.
