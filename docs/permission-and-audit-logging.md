# Permission Tiers and Audit Logging

This document describes the permissions currently enforced by the code and the log format for requests and AI activity. It distinguishes implemented behavior from the proposed integration contract for the team's AI system.

## Current permission tiers

The application defines two account roles: `customer` and `admin`. The backend checks permissions on every session-authenticated request. Hiding a button or page in the frontend is not an authorization control.

| Capability | Anonymous | Customer | Admin |
| --- | --- | --- | --- |
| Health check (`GET /api/health`) | Allowed | Allowed | Allowed |
| View active financing products (`GET /api/v1/financing/products`) | Allowed | Allowed | Allowed |
| Register (`POST /api/v1/auth/register`) | Creates a customer account | — | — |
| Sign in | Allowed | Allowed | Allowed |
| View session / sign out | Not allowed | Own session | Own session |
| Read or update profile (`/customers/me`) | Not allowed | Own profile | No admin profile endpoint currently exists |
| View dashboard / transactions | Not allowed | Own transactions | No access through current endpoints |
| Add a transaction | Not allowed | Own account | No access through current endpoints |
| Request financing recommendations | Not allowed | Uses own profile | No access through current endpoints |
| Create / view support tickets | Not allowed | Create and view own tickets | View all tickets |
| Change ticket status | Not allowed | Not allowed | Allowed |
| View customer list / profile by ID | Not allowed | Not allowed | Allowed |
| Manage roles, deactivate accounts, create admins | Not allowed | Not allowed | No endpoints currently exist |

Registration through the API creates only `customer` accounts. An `admin` account is bootstrapped from `ADMIN_EMAIL` and `ADMIN_PASSWORD` when the backend starts, if one does not already exist. There is no self-service role elevation.

### Endpoint scope

- Public: `GET /api/health`, `GET /api/v1/financing/products`, `POST /api/v1/auth/register`, and `POST /api/v1/auth/login`.
- Authenticated account: `GET /api/v1/auth/session` and `POST /api/v1/auth/logout`.
- Customer: `/api/v1/customers/me*`, `/api/v1/transactions*`, `POST /api/v1/financing/recommendations`, `POST /api/v1/assistant/chat`, `POST /api/v1/support/tickets`, and `GET /api/v1/support/tickets` (own tickets only).
- Admin: `GET /api/v1/customers`, `GET /api/v1/customers/:customerId`, `PATCH /api/v1/support/tickets/:ticketId`, and `GET /api/v1/support/tickets` (all tickets).

`GET /api/v1/customers/:customerId` returns more detailed profile data than the customer list. Treat it as restricted personal data; do not grant another role access without defining a new data scope.

## HTTP request logs currently emitted

The middleware writes one JSON Lines record for each completed HTTP response, including successful responses such as `200` and `201`, and error responses such as `400`, `401`, `403`, `429`, `500`, and `503`. Files are partitioned by UTC date at `backend/.data/logs/YYYY-MM-DD.jsonl`. The same record is also written to stdout or stderr.

Example `200 OK` record:

```json
{"timestamp":"2026-10-20T04:15:30.123Z","level":"info","event":"http_request","requestId":"9cc99a72-65ae-4904-97c6-67dc1517ff88","method":"GET","path":"/api/v1/customers/me","status":200,"durationMs":18.42,"actorRole":"customer"}
```

Fields currently emitted:

| Field | Meaning |
| --- | --- |
| `timestamp` | UTC timestamp in ISO 8601 format |
| `level` | `info` below 400, `warn` for 4xx, and `error` for 5xx |
| `event` | Event type; currently `http_request` |
| `requestId` | UUID for correlating a request; also returned in the `x-request-id` header |
| `method`, `path` | HTTP method and path; query strings are not logged |
| `status` | Response status code |
| `durationMs` | Time from the logging middleware until the response finishes |
| `actorRole` | Present when the request was authenticated, such as `customer` or `admin` |
| `errorType`, `errorCode` | Present when the error handler provides metadata; the request record does not include an error message or stack trace |

The current HTTP request log does not include the request body, query string, cookies, authorization headers, prompts, or response bodies. Log files are Git-ignored. Newly created files use permission `0600`. After a response finishes, the logger attempts to append the record; if the write fails, it emits `log_write_failed` to stderr.

## AI workflow logging and integration with the team's AI

### Current implementation status

The current assistant flow is short: validate a message, run the PII masker, send a request to an OpenAI-compatible endpoint, and extract the text result. The system currently records only the `http_request` event for `POST /api/v1/assistant/chat`. It has no per-step AI event logs, multi-step agent orchestration, or callback contract connected to the team's AI framework. If provider configuration is incomplete, the request returns `503` and still appears in the HTTP log.

The event schema below is a requirement for a future integration; these events are not emitted by the application today.

### Events the AI adapter should emit

The backend should receive events from the team's AI adapter and write them as structured JSONL, correlating the existing `requestId` with an AI `runId` and `stepId`:

1. `ai_run_started` when an AI run begins.
2. `ai_step_started` before each step, such as `input_validation`, `pii_masking`, `context_retrieval`, `provider_request`, or `response_validation`.
3. `ai_step_completed` when a step succeeds, with a safe outcome such as a result count or validation status.
4. `ai_step_failed` when a step fails, with a sanitized error class/code and whether a retry is appropriate.
5. `ai_run_completed` or `ai_run_failed` when the run ends, with an overall status and duration.

Example successful masking event (target schema only; not currently emitted):

```json
{"timestamp":"2026-10-20T04:15:30.124Z","level":"info","event":"ai_step_completed","requestId":"9cc99a72-65ae-4904-97c6-67dc1517ff88","runId":"ai-73b4a2","stepId":"step-02","step":"pii_masking","status":"success","durationMs":2.1,"result":{"inputAccepted":true,"redactionCount":2,"redactionTypes":["email","phone"]}}
```

Recommended shared fields for AI events: `timestamp`, `level`, `event`, `requestId`, `runId`, `stepId`, `step`, `status`, `durationMs`, `provider`, `model`, `attempt`, and a validated, sanitized `result` summary. For failures, use `errorType`, `errorCode`, `retryable`, and a safe summary. Do not log raw provider exception messages without sanitization.

### Integration contract for the AI team

The AI adapter should receive an event sink or callback from the backend instead of writing its own unstructured logs. The interface below is framework-agnostic and can be adapted to the team's stack:

```ts
type AiStepEvent = {
  runId: string;
  stepId: string;
  step: string;
  phase: "started" | "completed" | "failed";
  status?: "success" | "error";
  durationMs?: number;
  provider?: string;
  model?: string;
  resultSummary?: Record<string, string | number | boolean | string[]>;
  errorType?: string;
  errorCode?: string;
  retryable?: boolean;
};

type AiEventSink = (event: AiStepEvent) => void | Promise<void>;
```

The adapter should send only step names, statuses, and allowlisted summaries. It must not send prompts, completions, chain-of-thought, customer profiles, secrets, access tokens, or raw exceptions to the event sink. The backend should add `requestId`, `actorRole` when available, and a timestamp, then write through a shared logger. Do not let a provider choose `requestId` or write raw logs directly to shared storage.

If a summary originates as free-form model text, validate and convert it to a schema-defined enum or number before logging, such as `resultCount`, `schemaValid`, or `decisionCategory`. Avoid logging full natural-language responses because they may reveal user information.

### Data that must not appear in AI logs

- Do not log raw prompts, inputs, or outputs, including masked messages that may still contain business or financial details.
- Do not log names, email addresses, phone numbers, account numbers, national IDs, addresses, amounts, or other identifying data in `resultSummary`.
- Use opaque IDs (`requestId`, `runId`, `stepId`) and restrict access to logs.
- Redaction counts and types may be logged, but never the values before or after redaction.
- Never log secrets, API keys, cookies, authorization headers, credential-bearing provider URLs, or chain-of-thought.
- Define retention, deletion, encryption at rest, access auditing, and alerting before using real customer data.

## Reading local logs

```bash
# Follow today's log file using the UTC date
tail -F "backend/.data/logs/$(date -u +%F).jsonl"

# Show only successful 200 responses
jq 'select(.event == "http_request" and .status == 200)' "backend/.data/logs/$(date -u +%F).jsonl"

# Find records for a request ID
jq 'select(.requestId == "<request-id>")' "backend/.data/logs/$(date -u +%F).jsonl"
```

When the backend runs in an open terminal, JSONL records also appear on stdout/stderr. For a service or container, use the process manager/container log viewer and forward stdout to a centralized logging platform while preserving the schema.

## Operational gaps before production

- Add an AI run/step event sink using the contract above.
- Add domain audit events for sensitive changes, such as profile updates, transaction creation, and ticket updates, plus admin profile reads. Record opaque resource IDs and outcomes; do not store payloads.
- Add log rotation/retention, centralized collection, monitoring/alerts, and tests for log-store failures.
- Review and enforce the CSRF/origin policy before exposing the API beyond the local development environment.
- Use a shared rate-limit store for multiple instances and configure trusted proxies for the deployment.
