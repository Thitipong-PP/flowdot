# Flow — SME Finance Copilot

Flow is a two-service application. The Next.js frontend and Express API run independently and communicate over HTTP. MongoDB stores customer profiles/accounts, financing products, transactions, and support tickets.

## Project layout

```text
frontend/   Next.js App Router application
backend/    Express 5 API, MongoDB models, validation, and business services
```

## Requirements

- Node.js 20.9 or newer
- npm 10 or newer
- MongoDB 7 or a MongoDB Atlas connection string

## Install

From the repository root:

```bash
npm install
```

## Configure MongoDB and start the API

```bash
cp backend/.env.example backend/.env
```

For a local database, start MongoDB with Docker Compose:

```bash
docker compose up -d mongodb
```

The example URI in `backend/.env.example` connects to that local MongoDB instance. Set `AUTH_SECRET` to at least 32 random characters, plus `ADMIN_EMAIL` and a strong `ADMIN_PASSWORD`. You can replace `MONGODB_URI` with a MongoDB Atlas URI. Then start the API:

```bash
npm run dev:backend
```

The API listens on `http://localhost:4000`. Its health endpoint is `GET /api/health`.
Stop the local database with `docker compose down` (the named volume keeps its data).

### Inspect MongoDB

The default local connection uses database `flowdot`. Open MongoDB Compass and connect to:

```text
mongodb://127.0.0.1:27017/flowdot
```

Collections are created when data is first written: `customerprofiles`, `useraccounts`, `financingproducts`, `transactions`, and `supporttickets`. Alternatively, with `mongosh` installed, run `mongosh "mongodb://127.0.0.1:27017/flowdot"`, then use `show collections` and `db.customerprofiles.find().pretty()`.

MongoDB must be running first. With Docker installed, `docker compose up -d mongodb` starts it. To use another local or Atlas database, change `MONGODB_URI` in `backend/.env` and restart the backend.

## Start the frontend

On first setup, create the local frontend env file, then start the frontend in another terminal:

```bash
cp frontend/.env.example frontend/.env.local
npm run dev:frontend
```

The web app listens on `http://localhost:3000`. Edit `frontend/.env.local` if the API is hosted somewhere other than `http://localhost:4000/api/v1`. `NEXT_PUBLIC_API_URL` is a Next.js public build variable; restart the dev server after changing it, and rebuild/redeploy in production.

## API routes

- `POST /api/v1/auth/register` — create a customer profile/account and sign in; requires financial-data consent.
- `POST /api/v1/auth/login`, `GET /api/v1/auth/session`, `POST /api/v1/auth/logout` — manage a signed session.
- `GET/PATCH /api/v1/customers/me` — read or update the current customer profile.
- `GET /api/v1/customers/me/dashboard` — transaction totals and recent activity.
- `GET /api/v1/customers` and `GET /api/v1/customers/:customerId` — admin-only customer management.
- `GET /api/v1/financing/products` — list active financing products.
- `POST /api/v1/financing/recommendations` — match products to the signed-in customer's stored profile.
- `GET/POST /api/v1/transactions` — list or record the current customer's income/expenses.
- `POST /api/v1/support/tickets` and `GET /api/v1/support/tickets?status=open` — submit and list own tickets; admins can list all.
- `PATCH /api/v1/support/tickets/:ticketId` — update ticket status; admin role required.
- `POST /api/v1/assistant/chat` — send a message to a configured model after backend PII masking.

Authentication uses `POST /api/v1/auth/register` and `/api/v1/auth/login`, with an HttpOnly signed session cookie. Admin routes require a signed-in account with the admin role. Customer profile, transaction, dashboard, and support-ticket reads are scoped to the signed-in customer.

Seed the lender product examples, demo accounts, sample transactions, and a support ticket into the local database:

```bash
npm run seed --workspace=@flowdot/backend
npm run seed:demo --workspace=@flowdot/backend
```

The development admin and customer email/password values are in the ignored local file `backend/.env`. They are generated for this checkout; use new secrets before exposing the service to anyone else.

Every completed HTTP response is written as one JSON line to `backend/.data/logs/YYYY-MM-DD.jsonl`, including successful responses and 4xx/5xx/503 statuses. Logs contain method, path, status, request ID, and duration; they do not contain request bodies, cookies, or authorization headers. The log folder is ignored by Git. AI step-level events are not emitted yet; see the logging document for the proposed team integration contract.

The assistant route requires an OpenAI-compatible endpoint configured with `LLM_API_URL`, `LLM_API_KEY`, and `LLM_MODEL`. The backend PII masking boundary runs before any provider request. When these values are missing, chat returns HTTP 503 instead of a simulated answer. Do not configure a provider until its data-processing terms are approved for the financial information this app handles.

The complete OpenAPI 3.1 API contract is in [`backend/openapi.yaml`](backend/openapi.yaml). Import it into Swagger Editor, Postman, or Insomnia to explore the request and response schemas.

Security, permission tiers, current request-log fields, and the proposed AI step-event contract are documented in [`docs/permission-and-audit-logging.md`](docs/permission-and-audit-logging.md). The current implementation writes one HTTP completion record per response; per-step AI events are a documented integration requirement and are not emitted yet.

The current source/configuration self-assessment, known risks, and recommended production remediation are in [`docs/security-self-assessment.md`](docs/security-self-assessment.md). This is an initial code review, not a penetration test or compliance certification.

The seeded lender products, demo customer, example transactions, and ticket are sample data. Replace product terms with verified lender data before production use. The app currently supports real registration/login, profile updates, database-backed recommendations, transaction entry and summaries, support-ticket submission, and role-protected admin customer/ticket views. The chat panel is an in-app preview; no LINE webhook or messages are connected.

Receipt image upload/OCR, actual bank transaction imports, loan applications, password reset, email verification, MFA, and production identity/role administration are not implemented. The chat UI is connected to the assistant endpoint, but will show 503 until a provider is configured. PII masking uses pattern-based detection and cannot guarantee detection of every name or identifier in free text. Authentication rate limiting is in-memory per process; local JSONL logs have no automatic retention/rotation. Before production, deploy behind HTTPS, add distributed rate limiting and log rotation/monitoring, backups, retention rules, and a formal privacy/security review.
