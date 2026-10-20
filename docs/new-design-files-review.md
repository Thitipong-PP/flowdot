# Review of the New AI Design Files

Reviewed on 2026-10-20 against the current `AI/` implementation.

## Scope

The newly added files are the complete system architecture diagram, the main orchestrator flow, the Agentic RAG subflow, and the input/situation/output matrix. They describe 13 scenario groups, including three duplicate-detection cases.

## Implementation Status

| Scenario | Current status | Notes |
|---|---|---|
| 1. Exact Rich Menu fast path | Implemented in AI service | Deterministic route matching exists. Routes are sample URLs/contact details and must be replaced before production. |
| 2. Natural-language fast path | Implemented in AI service | Uses the local Ollama classifier when deterministic matching does not apply. |
| 3. Receipt/invoice OCR and cashflow | Partial | OCR, document classification, extraction, and cashflow simulation exist. Receipt confirmation is not a complete user-confirmed persistence workflow. |
| 4. Liquidity crisis and loan search | Partial | Orchestrator can invoke loan retrieval after a cashflow deficit. Profile values include fallback/sample values. |
| 5. Arithmetic mismatch guard | Partial | Deterministic guard exists and emits telemetry; the complete correction/review interaction from the matrix is not wired through the UI. |
| 6.1–6.3. Hard duplicate, reconciliation, soft duplicate | Not connected to the request pipeline | A duplicate-check helper exists in `VisionWorker`, but no production call site invokes it. Do not treat these cases as working. |
| 7. Bank statement extraction | Partial | Schema, extraction, totals, and consistency guard exist. Multi-page ingestion and persisted profile health updates are not complete. |
| 8. Direct loan request and 5-stage RAG | Partial | Retrieval, deterministic eligibility checks, recovery, and synthesis exist; data quality and real underwriting accuracy are not established. |
| 9. No eligible product diagnostics | Partial | Worker has rejection diagnostics, but the full actionable UI flow in the matrix is not complete. |
| 10. Collateral recovery / CRAG | Partial | Recovery logic exists in the loan worker; eligibility and product catalog need real-world validation. |
| 11. Zero or negative burn rate | Implemented in calculation worker | A zero-division guard exists. |
| 12. LINE Flex postback | Parser only | The endpoint parses action parameters. It does not validate LINE signatures, authorize the user, confirm an application, or persist the action. |
| 13. Debounce mixed inputs | Partial | In-memory debounce exists. It is process-local and is not durable or coordinated across multiple service instances. |

## Security Changes Made

- Protected `/api/v1/*` with a bearer token when `AI_SERVICE_TOKEN` is configured. Tokens shorter than 32 characters are rejected. Without a token, only loopback requests are allowed when `DEBUG=true`; otherwise API access fails closed.
- Added JSONL HTTP request logs for all response statuses, including successful responses. Logs contain method, route path, status, request ID, and latency, and omit bodies, query values, credentials, and user identifiers.
- Added size limits and PNG/JPEG/WebP signature checks for image uploads; generated random server filenames are used.
- Added persistent AI activity JSONL logs containing event/node/status metadata only. Model reasoning, user content, profile information, financial amounts, and result payloads are excluded.
- Replaced model-generated chain-of-thought telemetry with fixed activity summaries. The protected SSE response still carries the user-facing result needed by the chat UI; persisted activity logs never include it. Intermediate cash metrics are reduced to a risk category.
- Applied text PII masking before fast-path classification and before queuing ingress content for the orchestrator.
- Added `AI/.data/` and `AI/uploads/` to `.gitignore`.

Log locations at runtime:

- `AI/.data/logs/http-audit.jsonl`
- `AI/.data/logs/ai-activity.jsonl`

Both JSONL files rotate at 10 MB and retain up to seven backups.

## Remaining Security and Integration Gaps

1. The frontend reaches AI only through the authenticated Node backend. It receives prose responses; structured cashflow and loan cards are not currently rendered in the chat. Do not place `AI_SERVICE_TOKEN` in browser code.
2. The AI bearer token is service-wide, not user-scoped. A token holder can request a telemetry stream by choosing a `session_id`; bind stream access to the authenticated backend user's session before exposing the service beyond localhost.
3. Text masking does not redact uploaded image pixels. The current OCR flow sends original document images to the configured Typhoon OCR provider. This needs an explicit privacy/consent decision and an image redaction or approved processing workflow before using real customer documents.
4. The FastAPI service currently has no LINE signature verification or real postback confirmation workflow.
5. In-memory debounce, SSE subscribers, and retrieval state are process-local and do not scale horizontally without shared infrastructure.
6. Several fallback business profile values are sample data. The integrated Node path supplies customer-derived context and suppresses cashflow/loan calculations without a verified cash balance. AI service fallback paths must not be presented as verified eligibility or a binding financial offer.
7. There is no completed consent ledger or purpose-specific PDPA consent flow in the AI service.

The new diagrams and matrix are treated as a target design. They are not evidence that all described scenarios are production-complete.
