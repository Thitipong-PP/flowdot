# Live Demo (Real AI Run) : [Click Here](https://comp.suwapatsu.tech/)

# Flow — SME Finance Copilot

Flow is an SME Finance Copilot consisting of three coordinated services:
- **`frontend/`**: Next.js App Router application (Unified Web UI & in-app chat on `:3000`)
- **`backend/`**: Express 5 API with MongoDB models, session auth, validation, and business logic (`:4000`)
- **`AI/`**: FastAPI headless orchestrator, dual-model local LLM integration, hybrid FAISS vector retrieval, and financial workers (`:8000`)

The web UI on port `3000` is the single public entry point (ideal for routing through Cloudflare Tunnel for competition submission). All internal API calls are proxied securely to the Node API (`:4000`), which communicates with the FastAPI AI service (`:8000`) via protected server-to-server bearer tokens. Both services share a single unified MongoDB database (`flowdot`).

---

## Key Features

1. **Unified Web Experience (Port 3000)**:
   - Single, polished web application containing both the Customer Finance Copilot and the Operations Admin Console.
   - **Multi-Agent Live Execution Radar**: Visualizes in real time the 6 worker nodes (*Ingress & Router*, *Vision OCR*, *Cashflow Worker*, *Invariant Guard*, *5-Stage Agentic RAG*, *Response Compiler*).
   - **Real-Time Thought Stream Terminal**: Monospace streaming terminal showing deterministic step-by-step agent deliberations.
   - **Live Financial Diagnostics**: Instant visibility into projected cash balance, runway days, and risk tier.
   - **Quick Scenario Action Chips**: 1-click test scenarios for competition judges (e.g., 🚨 Urgent ฿95k repair bill, ✅ ฿15k supply invoice, 💬 Service intro, 🏦 SME loan search).
2. **Headless AI Subsystem**:
   - Pure headless backend logic with zero standalone web templates or redundant web servers.
   - Fast-Path routing (< 2ms deterministic responses), PII masking, and anti-hallucination guardrails.
3. **Single Configuration Point**:
   - Configure only one root `.env` file for the entire project. All sub-services (`backend/.env`, `frontend/.env.local`, `AI/.env`) are automatically kept in sync.

---

# AI Architecture

![AI Agent](asset/AI%20Agent.png)

## The Nature of Flow as an Autonomous AI Agent

Flow is not a simple linear chatbot or static retrieval script. It is designed as a **Hybrid-Hierarchical Autonomous Financial Agent** that perceives multi-modal inputs, deliberates through planning loops, invokes specialized domain tools, verifies mathematical invariants, and self-corrects:

- **Autonomous Planning & Deliberation (ReAct Cycle)**: Powered by a local LLM Master Orchestrator (`qwen2.5:3b` / `qwen3:4b`), the agent deliberates on every incoming message to analyze intent, dynamically select tools from its registry (`tool_vision`, `tool_cashflow`, `tool_loan_rag`), extract monetary figures, and compile execution strategies without hardcoded branching.
- **Two-Tier Ingress & Fast-Path Routing Filter**:
  - *Tier 1 (Sub-2ms Deterministic Filter)*: Intercepts static system commands and non-financial menu keys (e.g., login links, support contact) in sub-2ms without consuming LLM compute or tokens.
  - *Tier 2 (Debounce Buffer & Concurrency Lock)*: Automatically batches rapid multi-modal uploads (e.g., users sending 2–3 slip photos and text in rapid succession) within a 3–5 second window with per-user mutex locks to prevent race conditions.
  - *Thai PII Masking*: Anonymizes sensitive national ID cards, bank account numbers, and phone numbers before any text reaches the LLM.
- **Hierarchical Dual-Model Architecture**:
  - *Master Brain (3B/4B)*: Manages high-level reasoning, multi-turn dialogue, tool orchestration, and financial advice synthesis.
  - *Satellite Worker (1.7B)*: Fast, zero-temperature specialist executing low-latency classification, document metadata parsing, and underwriting rationales.
- **Specialized Tool Ecosystem**:
  - 👁️ **Vision Worker**: Integrates real Typhoon OCR API to extract payment slips, tax invoices, and bank statements with a 3-tier duplicate detection engine (image perceptual hashing + exact text + semantic matching).
  - 💰 **Cashflow Simulation Worker**: Deterministically computes daily burn rates, liquidity runway days, and projected balances with zero-division safety guards.
  - ⚖️ **Invariant Sanity Guard (Anti-Hallucination)**: 100% Pure-Python algebraic guard verifying that all numbers stated by the LLM strictly adhere to physical financial laws (Projected = Current + Inflow - Outflow, VAT 7%, WHT 3%), vetoing and correcting any arithmetic hallucination.
  - 🏦 **5-Stage Financial Agentic RAG Worker**: Autonomous underwriter and loan matcher operating over real Bank of Thailand catalog data.
- **Real-Time Observability & Live Telemetry**: Streams every internal thought, active node state, and execution wire via Server-Sent Events (SSE) directly to the web UI's Multi-Agent Radar.
- **Interactive UI Compiler**: Formats structured responses into rich interactive visual cards, summary bubbles, and loan carousels.

---

## 5-Stage Agentic RAG Pipeline

![Agentic RAG](asset/Agentic%20RAG.png)

When liquidity deficits or financing inquiries are detected, the agent launches the **5-Stage Financial Agentic RAG Sub-flow**, simulating a human banking credit underwriter through deterministic validation and self-correcting retrieval loops:

1. **Stage 1: Pre-Retrieval Context Synthesis**:
   - Synthesizes an augmented natural-language query from the customer's live financial profile (monthly gross revenue, existing debt service, DSCR ratio, business age, collateral availability, and current deficit).
   - Prepares dense vector search representations using `intfloat/multilingual-e5-small` with the `"query: "` prefix without hardcoded if/else rules.
2. **Stage 2: Dual-Mode In-Memory Hybrid Search (RRF K=60, Latency < 20ms)**:
   - *Dense Retrieval*: In-memory FAISS (`IndexFlatIP`) computing Cosine Similarity across 384-dimensional semantic embeddings.
   - *Sparse Retrieval*: `BM25Okapi` performing Thai and English tokenized keyword matching against contextual summary headers.
   - *Reciprocal Rank Fusion (RRF)*: Merges dense and sparse ranks with constant k=60 to retrieve the Top 5–10 candidate loan products from Thai commercial banks in under 20ms.
3. **Stage 3: Deterministic Underwriting Guard (Pure Python Grader)**:
   - Evaluates non-negotiable commercial credit constraints in pure Python code (Zero LLM Hallucination):
     - Minimum monthly revenue thresholds (e.g., ฿50k – ฿200k)
     - Minimum operating business age (e.g., 6 months to 2 years)
     - Maximum borrowing capacity based on monthly revenue
     - Debt Service Coverage Ratio (DSCR) feasibility
     - Mandatory collateral or guarantor requirements
4. **Stage 4: CRAG (Corrective RAG) Self-Correction Recovery Loop**:
   - *Diagnostic Evaluation*: Checks if at least 2 qualified loan products passed Stage 3.
   - *Query Relaxation Loop*: If candidates are insufficient due to missing collateral or strict age requirements, CRAG analyzes the rejection diagnostics and triggers dynamic query rewriting to search for alternative unsecured loans, clean loans, or TCG/SME D Bank PGS full-credit guarantee schemes, re-executing Stage 2.
   - *Deterministic Guard Fallback*: If all standard commercial bank loans are denied (e.g., SME monthly revenue < ฿50,000), the guard strictly prevents hallucinating or recommending unqualified bank loans. Instead, it safely routes to an actionable Micro/Nano Finance advisory and government opportunity fund guidance.
5. **Stage 5: Live Synthesis & Recommendation**:
   - The Satellite LLM (`qwen3:1.7b`) synthesizes personalized recommendation rationales tailored specifically to the SME's actual financial ratios.
   - Formats product terms, starting rates, and credit limits, and compiles an actionable loan application document checklist.

---

## Project Layout

```text
├── .env                  Single central configuration file for all services
├── frontend/             Next.js App Router unified web client (:3000)
├── backend/              Express 5 API & MongoDB models (:4000)
├── AI/                   FastAPI headless AI orchestrator & retrieval (:8000)
├── docs/                 Project documentation, security, and architecture
│   ├── architecture/     System diagrams, workflows, and test case matrices
│   └── references/       Design templates and onboarding domain data
├── scripts/              Cross-platform runners, seeders, and env synchronizer
├── compose.yaml          Docker Compose configuration for local MongoDB
└── package.json          Root workspace scripts and unified task runner
```

---

## Requirements

- **Node.js** 20.9 or newer & **npm** 10 or newer
- **Python** 3.11 or newer (for the AI service)
- **MongoDB** 7 (local service or via `docker compose up -d mongodb`)
- *(Optional)* **Ollama** with models `qwen2.5:3b` and `qwen3:1.7b` for local AI inference

---

## Quick Start (Unified Setup)

### 1. Install Dependencies

From the repository root:

```bash
# Install Node workspaces
npm install

# Setup Python virtual environment for the AI service
python -m venv AI/.venv

# Windows:
.\AI\.venv\Scripts\pip install -r AI/requirements.txt
# Linux / macOS:
# ./AI/.venv/bin/pip install -r AI/requirements.txt
```

### 2. Configure Environment (Single Place)

Copy the central environment file:

```bash
cp .env.example .env
```

All configurations (database URIs, ports, service tokens, demo credentials) live in this single `.env` file. Running `npm run dev`, `npm start`, or `npm run seed` will automatically propagate settings to `backend/.env`, `frontend/.env.local`, and `AI/.env`.

### 3. Start MongoDB

If MongoDB is installed locally as a Windows service, it runs automatically. Alternatively, start it via Docker Compose:

```bash
docker compose up -d mongodb
```

### 4. Seed Database (One Command)

Seed backend demo accounts, sample transactions, financing products, and the AI loan catalog embeddings simultaneously:

```bash
npm run seed
```

*(You only need to run this once or whenever you want to reset demo data).*

---

## How to Run

### Development & Testing (Hot Reload)

For active testing and quick changes:

```bash
npm run dev
```

This starts all 3 services concurrently in development mode:
- **Unified Frontend UI**: `http://localhost:3000`
- **Backend API**: `http://localhost:4000` (Health: `GET /api/health`)
- **AI Subsystem**: `http://127.0.0.1:8000` (Health: `GET /health`)

---

### Final Production Version (For Competition & Turn-in)

To run the final version with 1 single command in 1 terminal:

```bash
npm run prod
```

This automated all-in-one command will:
1. Seed the database (`npm run seed`) with demo accounts, transactions, and vector embeddings.
2. Build the optimized Next.js frontend (`npm run build:frontend`).
3. Start all 3 services concurrently (`npm start`) in production mode.

This starts:
- Frontend on `http://localhost:3000` running optimized static + SSR production build (`next start`)
- Backend API on `http://localhost:4000` in production mode
- AI Headless Subsystem on `http://127.0.0.1:8000`

---

## Pre-seeded Accounts & Quick Login

In the web UI at `http://localhost:3000`, open the login modal and click either **⚡ Demo SME** or **🛡️ Admin Demo** for 1-click instant credential filling:

- **Demo Customer**:
  - Email: `customer@example.com`
  - Password: `Customer12345678!`
- **Admin**:
  - Email: `admin@example.com`
  - Password: `Admin12345678!`

---

## Cloudflare Tunnel Setup (For Competition Submission)

Because the Next.js frontend on port `3000` internally proxies `/api/*` to the backend, you only need to expose **port 3000**:

```bash
cloudflared tunnel --url http://localhost:3000
```

Use the generated `*.trycloudflare.com` URL as your public submission link.

---

## API & Architecture Reference

- **OpenAPI Specification**: [`backend/openapi.yaml`](backend/openapi.yaml)
- **Architecture & Workflow Diagrams**:
  - [System Architecture](docs/architecture/system_architecture_complete.mmd)
  - [Main Orchestrator Flow](docs/architecture/main_orchestrator_flow.mmd)
  - [Agentic RAG Subflow](docs/architecture/agentic_rag_subflow.mmd)
  - [Input / Situation / Output Matrix](docs/architecture/all_cases_input_situation_output_matrix.md)
- **Security & Audit**:
  - [Permission & Audit Logging](docs/permission-and-audit-logging.md)
  - [Security Self-Assessment](docs/security-self-assessment.md)
  - [Design Coverage Review](docs/new-design-files-review.md)
