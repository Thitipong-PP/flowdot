# Security Self-Assessment Report

| Item | Details |
| --- | --- |
| System | Flowdot — SME Finance Copilot |
| Assessment date | 2026-10-20 |
| Scope | Source code and configuration for the Next.js frontend, Express API, MongoDB, session authentication, permission tiers, request logging, and the FastAPI AI service integration |
| Assessment type | Initial source-code and configuration review. This is not a penetration test, independent audit, certification, or legal compliance determination. |

## 1. Permission-Tier Implementation & Enforcement

### Permission tiers

| Tier / Principal | Permissions enforced by the backend | Restrictions |
| --- | --- | --- |
| Anonymous | Check service health, view active financing products, register a customer account, and log in | Cannot read or modify account or customer data |
| Customer | Read and update their own profile; view their own dashboard and transactions; create transactions; create and view their own support tickets; request financing recommendations based on their own profile; use the assistant | Cannot read another customer's data or transactions, change ticket status, or change their role |
| Admin | View the customer list and individual customer profiles; view all support tickets; change ticket status | No account or role management endpoint; no endpoint in the current API for reading or modifying customer transactions |
| AI assistant (service integration) | Receives authenticated customer messages through Node, after consent checks and PII masking; receives minimized numeric profile context and can run cashflow calculations or retrieve financing products in the AI service | It is not a user role and has no tool for calling application APIs, modifying/deleting records, approving loans, or escalating privileges; it has no `admin` role. Node does not expose a customer database connection to the model. |

Registration through the API creates only `customer` accounts. Admin accounts are bootstrapped from `ADMIN_EMAIL` and `ADMIN_PASSWORD` by the backend. There is no self-service role elevation. See [Permission tiers and audit logging](permission-and-audit-logging.md) for the endpoint-level mapping.

### Enforcement

Authorization is enforced in backend code, not by prompt instructions or hidden frontend controls. The `authenticate` middleware validates the session and account state against MongoDB. The `requireRole('admin')` middleware protects admin routes. Controllers use the `customerId` from the authenticated session to scope customer queries; transaction, ticket, and dashboard ownership is not selected using a client-supplied owner ID.

The Node chat route requires an authenticated customer and `financialDataConsent`, derives the customer identity from the session, masks the message, and sends a minimized context to FastAPI with a server-only bearer token. The AI orchestrator can call its cashflow and financing retrieval workers; these are not application mutation APIs. A system prompt telling the AI not to delete data is not a security boundary. Any future tool that reads or mutates application data must be explicitly allowlisted and enforce the same backend authorization used by application users. Never expose admin or database credentials to the model.

## 2. Known-Risk List & Controls

Risk levels are preliminary assessments based on potential impact and source-code review; they have not been validated through active exploitation. “Partial” means a control exists but is insufficient for production use.

| ID | Risk | Severity | Existing controls | Gap / recommended treatment |
| --- | --- | --- | --- | --- |
| R-01 | PII masking may miss names or identifiers in free-form text before it is sent to the AI service/provider, particularly Thai text or formats that do not match the regular expressions | **High** | Node's authenticated assistant controller calls `maskPii` before sending text to FastAPI; the AI service also applies its text masker | Masking is pattern-based and does not fail closed when uncertain. Restrict data with an allowlist, test Thai-language inputs, block provider calls if sanitization fails, and do not use real customer data before privacy review |
| R-02 | Mutation requests without an `Origin` header pass the origin middleware, weakening CSRF protection for session-cookie requests | **High** | CORS uses an origin allowlist and the session cookie uses `SameSite=Lax`; requests with a disallowed Origin are rejected | `requireTrustedOrigin` checks only when the header exists. Reject missing Origin on browser mutations or add a CSRF token, with a separate policy for trusted service clients |
| R-03 | Prompt injection or inaccurate financial guidance could mislead users into believing that a lender has approved financing | **Medium** | The current assistant has no tools for changing application data; its system instruction says it cannot approve loans on behalf of lenders | Prompt instructions are not enforcement, and model output can still be wrong. Validate output, communicate limitations, test adversarial prompts, and require human review for consequential decisions |
| R-04 | AI step logs do not yet include a complete run lifecycle, retry model, or centralized collection | **Medium** | FastAPI writes safe orchestrator event/node/status metadata to rotating JSONL, correlated by request ID; Node logs the upstream status and duration, including 200 and failures | Add validated run/step IDs, centralized retention/alerting, and sink-failure monitoring; never log raw prompts, model reasoning, financial values, or outputs |
| R-05 | Rate limiting uses process-local memory, and trusted proxy behavior is not configured | **Medium** | Login and registration attempts are limited within each process | Limits reset on restart and are not shared across instances. Use a shared store and configure trusted proxies for the deployment |
| R-06 | Admin can read detailed customer profiles, and the only roles are `customer` and `admin` | **Medium** | Admin routes require `requireRole`; the customer list returns only selected fields | Apply least privilege and scoped permissions, minimize fields by job function, add MFA, and audit access to personal data |
| R-07 | Consent and compliance controls may not cover distinct purposes or the full data lifecycle | **High** | Registration requires `financialDataConsent: true` | There is one boolean flag, without purpose, notice version, timestamp, or a separate withdrawal mechanism. The system has not had a legal/PDPA review. Design consent records, privacy notices, retention/deletion, and data-subject rights with qualified privacy/legal review |
| R-08 | Local logs have no rotation, retention policy, or centralized alerting; log writes are asynchronous | **Medium** | Daily JSONL files record successful and failed HTTP responses and are also written to stdout/stderr | Logs may grow without limit or be lost on abrupt process termination. Add centralized collection, retention, access control, alerting, and log-sink failure testing |
| R-09 | Demo seed data and admin bootstrap could be used in the wrong environment | **Medium** | Values are read from environment variables, `.env.example` uses placeholders, and `.env`/runtime logs are Git-ignored | Disable demo seeding in production, use a secret manager, make admin bootstrap one-time, and reject default/example credentials during deployment |
| R-10 | MFA, email verification, password reset, and account recovery are not implemented | **Medium** | Passwords use `scrypt`; signed sessions can be revoked through `sessionVersion` | Add recovery, verification, MFA, and session/device administration before production use |
| R-11 | A log-write failure prints `error.message` to stderr | **Low–Medium** | HTTP request records do not include bodies, cookies, or authorization headers | Sanitize or allowlist logged metadata and prevent paths or credentials from appearing in centralized logs |
| R-12 | Uploaded financial images can contain unmasked PII and are sent to an external OCR provider | **High** | Text sent to the AI service is masked; images are size/type checked but their pixels are not redacted before Typhoon OCR | Do not send real customer documents until image redaction or an approved processing/consent flow is implemented and provider terms, data residency, retention, training use, and subprocessors are reviewed |

## 3. Data Protection & Privacy

Before calling the AI service, the Node API masks the user message and sends only that text plus a minimized numeric context derived from the authenticated customer's recorded transactions and profile. It checks the existing `financialDataConsent` flag and does not send customer name, email, phone, transaction descriptions, or raw profile fields. The transaction ledger has no opening/current cash balance, so the backend sends `current_cash: null`; the orchestrator suppresses cashflow and loan calculations that depend on a verified cash balance. The masker is pattern-based, so free-form PII can still be missed. Uploaded image pixels are not masked; when Typhoon OCR is configured, the original image is sent to that external provider. Do not use real customer images until a suitable redaction or approved data-processing and consent flow is in place. Operational AI logs omit prompts and result payloads.

Registration requires `financialDataConsent` to be `true`, but this is a single flag on the customer profile. Consent is not separated by purpose, such as service delivery, financing recommendations, sharing data with an LLM, analytics, or marketing. The system also lacks records of the notice text/version, time and method of consent, withdrawal, or purpose-specific retention. Therefore, this report **does not conclude that the system is PDPA-compliant**. Define the lawful basis and appropriate consent by purpose, together with privacy notices, data minimization, retention/deletion, and data-subject request processes, and obtain qualified privacy/legal review before production use.

## Optional Sections

### Overview & Threat Model

The system consists of a Next.js frontend, an Express API, MongoDB, and a protected FastAPI AI service. The API uses signed cookie sessions and calls AI server-to-server with a bearer token. Threat actors considered include unauthenticated users, customers attempting to access other customers' data, compromised admin accounts, browser-based CSRF, prompt injection in user messages, log-based data exposure, and third-party OCR providers receiving original images.

The primary trust boundaries are backend authorization, database ownership filters, input validation, and the LLM gateway/masking boundary. Hidden UI controls and system prompts are not trust boundaries. This assessment does not cover cloud infrastructure/IAM, production network configuration, MongoDB deployment, backup systems, or a provider that has not yet been selected.

### Authentication & Secrets Management

- Passwords use Node.js `scrypt` with a random salt and constant-time comparison.
- Sessions use HMAC-SHA256-signed tokens. Authenticated requests re-check account status, role, and `sessionVersion` in MongoDB.
- Cookies use `HttpOnly` and `SameSite=Lax`; `Secure` is enabled when `NODE_ENV=production`.
- The backend refuses to start if `AUTH_SECRET` is missing or shorter than 32 characters. Admin/demo credentials and the LLM key are read from environment variables.
- `.env` files and local logs are Git-ignored. No secret-manager integration was found in this codebase; use the deployment's secret manager and never use demo credentials in production.

### Logging & AI Integration

The Node middleware writes one JSONL record for each completed HTTP response, including `200` responses. Records contain a timestamp, level, event, request ID, method, path, status, duration, and actor role when authenticated. Request bodies, query strings, cookies, and authorization headers are not included. Node writes to `backend/.data/logs/YYYY-MM-DD.jsonl`; FastAPI writes HTTP and safe AI activity logs to `AI/.data/logs/`, rotating at 10 MB with up to seven backups.

The AI orchestrator emits per-step event/node/status records and shares the Node request ID. The current stream authorization uses one service-wide token and does not bind a requested `session_id` to an end-user identity. Do not expose AI telemetry streams beyond the trusted service boundary until user-scoped session authorization is implemented. Continue to omit raw prompts, model output, chain-of-thought, PII, and secrets.

### Testing Performed

- Reviewed routes, middleware, controllers, and configuration to check permission tiers and data scoping.
- Reviewed the request logger source to confirm it records completed responses, including successful and error status codes. No load test or log-storage fault injection was performed.
- Reviewed the PII masker-to-LLM gateway path. No red-team test, PII-pattern coverage test, or real-provider test was performed.
- No penetration test, dependency vulnerability scan, cloud/IAM review, MongoDB backup/restore test, or formal PDPA/legal review was performed.
- This review is not evidence that the system has no vulnerabilities. Run automated security tests and obtain an external review before production.

### Third-Party Components & Licenses

Runtime components identified from the manifests include Next.js, React, Express, Mongoose, the MongoDB server image used by Compose, Helmet, CORS, and Zod. The AI provider is an external OpenAI-compatible endpoint selected by the deployer through environment variables.

No license inventory/SBOM or transitive-dependency vulnerability scan has been performed, and the intended LLM provider/terms are not yet known. Before production, review `package-lock.json` and container image versions, generate an SBOM, scan for CVEs, and review licenses and provider terms.

## Recommended Actions Before Production

1. Add an AI data allowlist and fail closed when PII masking or validation fails; implement image redaction before external OCR.
2. Fix CSRF/origin validation and test mutations from browsers and trusted service clients.
3. Design purpose-specific consent and obtain privacy/legal review; do not claim PDPA compliance before the review is complete.
4. Add AI run lifecycle events, domain audit trails, centralized log retention/access controls, and alerting.
5. Add shared rate limiting, trusted proxy configuration, admin MFA/least privilege, and account recovery.
6. Disable demo seeding and credentials in production; use a secret manager and review dependencies/licenses/SBOM.
7. Perform threat-based security testing, penetration testing, and deployment-specific review.
