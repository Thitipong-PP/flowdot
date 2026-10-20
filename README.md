# Flow — SME Finance Copilot

Flow runs as three separate services: a Next.js frontend, an Express/MongoDB API, and a FastAPI AI service. The browser calls only the authenticated Node API; the Node API calls AI over a server-to-server bearer token.

## Project layout

```text
frontend/   Next.js App Router application
backend/    Express 5 API, MongoDB models, validation, and business services
AI/         FastAPI orchestrator, workers, and retrieval service
```

## Requirements

- Node.js 20.9 or newer
- npm 10 or newer
- MongoDB 7 or a MongoDB Atlas connection string
- Python 3.11 or newer for the AI service

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

## Configure and start the AI service

The chat endpoint now calls the FastAPI orchestrator. Configure the same randomly generated `AI_SERVICE_TOKEN` in `backend/.env` and `AI/.env`; keep it server-side and never add it to a `NEXT_PUBLIC_*` variable. The repository's local ignored env files are already configured for this checkout. For a new checkout:

```bash
cp AI/.env.example AI/.env
```

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`, then put that same value in both env files. Set `AI_SERVICE_URL=http://127.0.0.1:8000` in `backend/.env`.

Install the AI dependencies once, then run the service in its own terminal:

```bash
python3 -m venv AI/.venv
AI/.venv/bin/pip install -r AI/requirements.txt
AI/.venv/bin/python -m uvicorn app.main:app --app-dir AI --host 127.0.0.1 --port 8000
```

AI health is shown as `reachable` when the API responds. This checks API reachability only; it does not guarantee MongoDB retrieval or Ollama model readiness. The authenticated Node chat route passes a minimized numeric context derived from the signed-in customer's consented profile and recorded transactions. Since the transaction ledger has no opening/current balance, the integration marks current cash as unavailable and suppresses cashflow and loan calculations that would require it. The AI service keeps its own `fintech_copilot` database for its product catalog.

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
- `POST /api/v1/assistant/chat` — send a message through the authenticated Node API to the protected AI service after backend PII masking and customer consent checks.

Authentication uses `POST /api/v1/auth/register` and `/api/v1/auth/login`, with an HttpOnly signed session cookie. Admin routes require a signed-in account with the admin role. Customer profile, transaction, dashboard, and support-ticket reads are scoped to the signed-in customer.

Seed the lender product examples, demo accounts, sample transactions, and a support ticket into the local database:

```bash
npm run seed --workspace=@flowdot/backend
npm run seed:demo --workspace=@flowdot/backend
```

The development admin and customer email/password values are in the ignored local file `backend/.env`. They are generated for this checkout; use new secrets before exposing the service to anyone else.

Every completed HTTP response is written as one JSON line to `backend/.data/logs/YYYY-MM-DD.jsonl`, including successful responses and 4xx/5xx/503 statuses. Logs contain method, path, status, request ID, and duration; they do not contain request bodies, cookies, or authorization headers. The log folder is ignored by Git. AI step-level events are not emitted yet; see the logging document for the proposed team integration contract.

The AI service uses its configured Ollama models and loan catalog. The backend logs the AI upstream status and duration without logging message content; the AI service records safe request and step metadata in `AI/.data/logs/`. AI chat is disabled until `AI_SERVICE_URL` and a matching 32-character-or-longer `AI_SERVICE_TOKEN` are configured. Text masking is pattern-based and can miss identifiers in free text.

The complete OpenAPI 3.1 API contract is in [`backend/openapi.yaml`](backend/openapi.yaml). Import it into Swagger Editor, Postman, or Insomnia to explore the request and response schemas.

Security, permission tiers, current request-log fields, and AI activity logging are documented in [`docs/permission-and-audit-logging.md`](docs/permission-and-audit-logging.md). AI activity logs contain node/status metadata but omit prompts, result payloads, and financial amounts.

The current source/configuration self-assessment, known risks, and recommended production remediation are in [`docs/security-self-assessment.md`](docs/security-self-assessment.md). This is an initial code review, not a penetration test or compliance certification.

The seeded lender products, demo customer, example transactions, and ticket are sample data. Replace product terms with verified lender data before production use. The app currently supports real registration/login, profile updates, database-backed recommendations, transaction entry and summaries, support-ticket submission, and role-protected admin customer/ticket views. Authenticated text chat uses the Node-to-FastAPI AI integration; the chat UI remains an in-app preview, and image/file uploads and LINE webhook/messages are not connected.

Frontend receipt/file upload controls are not connected to AI yet; the AI upload endpoint is available only as an internal API. The FastAPI postback route is a parser and is not a verified LINE webhook. Customer financial amounts sent to AI are derived from recorded transactions after consent; current cash is omitted because the ledger lacks an opening balance. Uploaded image pixels are not redacted before the optional Typhoon OCR provider. Do not send real documents until image handling and provider consent are reviewed. Authentication rate limiting is in-memory per process. Local logs rotate, but have no centralized collection or retention policy. Before production, add user-scoped authorization for AI telemetry sessions, distributed rate limiting, approved provider terms, backups, data retention/deletion processes, and formal privacy/security review.
