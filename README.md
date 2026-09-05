# RazorRecover

RazorRecover is a **risk-aware, constrained revenue-recovery decisioning system** for failed payment transactions. An LLM-based decision agent *recommends* a recovery action, a **deterministic Policy Engine authorizes** it, an **Execution Layer performs** it, and an **audit trail records** the entire decision — all surfaced to merchants through a read-only dashboard.

It is not "an AI agent that retries failed payments." It is a reference architecture and working prototype for deciding **whether, how, and when** a failed payment should be recovered — with ML risk/recovery scoring, RAG-augmented policy context, a hard safety shield, and full merchant visibility into every decision.

> **Prototype scope.** All policies, knowledge-base documents, training data, and gateway/notification providers in this repository are **synthetic demo material**. Nothing here contacts a real payment system, and this is **not** a Razorpay product or integration.

---

## Problem

Payments fail for many reasons — insufficient funds, bank declines, authentication failures, network timeouts, gateway errors, and expired cards. Revenue recovery after a failure is tricky:

- **Not every failure should be retried.** Blind retries create customer friction (repeated charges, dunning fatigue) and burn gateway goodwill.
- **Failures differ in recovery potential.** Some are best retried immediately, some after a delay, some via an alternative payment method, and some should simply stop.
- **Some cases require review.** High-value transactions and high-risk payments should never auto-fly through the system — a human should look first.
- **Merchants need visibility.** Merchants must be able to see *why* a decision was made, which policy version authorized it, and what actually executed — not just a final status.

A recovery system therefore needs more than a retry loop. It needs **risk assessment**, **context**, **constrained decisioning**, and **auditability**.

---

## Solution

RazorRecover treats recovery as a **decision pipeline with a hard safety boundary**. An AI agent alone never executes anything — its output is only a *recommendation* that a deterministic engine must authorize.

A failed payment flows through the pipeline as:

```
Failed Payment
     ↓
Context / Data
     ↓
ML Risk + Recovery Prediction
     ↓
RAG Policy Context
     ↓
LLM Decision Agent (recommends)
     ↓
Deterministic Shield / Policy Engine (authorizes)
     ↓
Execution (performs — only on ALLOW)
     ↓
Decision + Audit (records)
     ↓
Merchant Dashboard (reads)
```

### Core decision principle

```
AI recommends → Policy authorizes → Execution performs → Audit records
```

| Layer | Responsibility | Outcome |
| --- | --- | --- |
| ML models | Score each failed transaction | `risk_score`, `recovery_probability` (both in [0, 1]) |
| RAG | Retrieve merchant-relevant recovery/policy knowledge | Top-k context chunks |
| LLM decision agent | Recommend one action from a fixed allowed set | `AgentDecision` (structurally validated) |
| Deterministic Shield | Authorize or reject the recommendation with **no LLM involvement** | `ALLOW` / `REVIEW` / `BLOCK` + per-rule rationale |
| Execution layer | Perform the authorized action (and only that action) | Persisted `RecoveryAttempt` + status |
| Audit trail | Record the full decision trail | Immutable `AuditLog` per evaluation |

The allowed actions the agent may recommend are: `RETRY_NOW`, `DELAYED_RETRY`, `ALTERNATIVE_PAYMENT`, `CUSTOMER_NOTIFICATION`, `MANUAL_REVIEW`, and `STOP`. Only a deterministic **`ALLOW`** decision authorizes execution; `REVIEW` escalates to human review; `BLOCK` means nothing runs. The engine **fails closed**: missing data or an unexpected error can never accidentally authorize an action.

---

## Architecture

```mermaid
flowchart TD
    P[Failed Payment / Transaction] --> API[FastAPI API]
    API --> CTX[Context Assembly]
    CTX --> ML[ML Risk + Recovery Prediction]
    CTX --> RAG[RAG Policy Retrieval]
    ML --> AGENT[LLM Decision Agent]
    RAG --> AGENT
    AGENT --> SHIELD[Deterministic Shield / Policy Engine]
    SHIELD -->|ALLOW| EXEC[Execution Layer]
    SHIELD -->|REVIEW| REVIEW[Manual Review Escalation]
    SHIELD -->|BLOCK| BLOCK[No Execution]
    EXEC --> AUDIT[Decision + Audit Persistence]
    REVIEW --> AUDIT
    BLOCK --> AUDIT
    AUDIT --> DASH[Merchant Dashboard Read APIs]
    DASH --> UI[React Dashboard]

    subgraph async[Optional Async Path (Redis + Celery)]
        API -->|enqueue| Q[Recovery Task Queue]
        Q --> W[Celery Worker]
        W --> CTX
    end
```

The API surface is intentionally thin. Business logic lives in the **`RecoveryOrchestrator`** pipeline (`src/razor_recover/workflow/orchestrator.py`), whose stage boundaries are wired as injected ports so each layer can be swapped or faked in tests. The same orchestrator is used by both the synchronous endpoint and the asynchronous Celery path.

Read more: [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md).

---

## How the recovery workflow runs end-to-end

One evaluation of a failed transaction runs nine steps against the persisted record:

| Step | Stage | What happens |
| --- | --- | --- |
| 1 | Fetch transaction | Look up the failed payment and its context. |
| 2 | ML prediction | Logistic-regression models emit `risk_score` and `recovery_probability`. |
| 3 | RAG retrieval | Best-effort top-k policy/context chunks from Qdrant, scoped to the merchant. |
| 4 | LLM decision | Ollama-backed agent returns a *validated* JSON recommendation from the allowed-action set. |
| 5 | Policy authorization | 11 deterministic shield rules (no LLM) decide `ALLOW` / `REVIEW` / `BLOCK`. |
| 6 | Execution | Only on `ALLOW` — maps actions to mock gateway/notification providers. |
| 7 | Persist decision | `RecoveryDecision` row is written. |
| 8 | Audit | `AuditLog` row captures scores, RAG refs, the LLM rationale, every rule result, policy version, and execution status. |
| 9 | Respond | Return the `EvaluateResponse` to the caller. |

Both the synchronous endpoint (`POST /api/v1/recovery/evaluate`) and the asynchronous path (`POST /api/v1/recovery/evaluate/async` + `GET /api/v1/recovery/tasks/{task_id}`) run this exact pipeline.

---

## Merchant dashboard

A React 19 + Vite + TypeScript SPA (`frontend/`) consumes the read APIs through a typed client. It reads persisted data only; the only action it can trigger is enqueuing an evaluation (which the backend still owns).

| Screen | Route | Purpose |
| --- | --- | --- |
| Recovery Command Center | `/` | KPIs, recovery-outcome chart, risk distribution, recovery-probability buckets, insights, recent failed payments. |
| Transactions Investigation | `/transactions` | Filterable, paginated table of failed transactions with a summary strip. |
| Transaction Details | `/transactions/:id` | Overview, failure context, AI analysis, shield decision, recovery history, audit trail, decision timeline, and an "Evaluate Recovery" action. |
| Audit Logs | `/audit` | Paginated, transaction-filterable audit trail of every recovery decision. |

Read more: [`frontend/README.md`](frontend/README.md).

---

## Components

| Path | Responsibility |
| --- | --- |
| `src/razor_recover/api/` | FastAPI transport — thin endpoints that delegate to services (`/api/v1/...`). |
| `src/razor_recover/workflow/` | `RecoveryOrchestrator` — the coordinate pipeline `fetch → ML → RAG → LLM → Policy → Execution → persist → audit`. |
| `src/razor_recover/brains/ml/` | Feature builder, risk + recovery logistic-regression models, training/evaluation, lazy-loading prediction service. |
| `src/razor_recover/brains/rag/` | Embeddings (hash-based by default, Ollama optional), Qdrant vector store, retriever, chunking, synthetic knowledge base, seeding. |
| `src/razor_recover/brains/llm/` | Decision agent, Ollama provider, prompt building, strict output parsing/validation. |
| `src/razor_recover/shield/` | Deterministic policy engine — 11 rules, evaluator, `ALLOW` / `REVIEW` / `BLOCK` decision contract. |
| `src/razor_recover/execution/` | Recovery execution — mock payment gateway, mock notification provider, retry service. |
| `src/razor_recover/tasks/` | Celery app + async `recovery.evaluate_async` task (a thin adapter over the same orchestrator). |
| `src/razor_recover/services/read/` | `DashboardReadService` — all dashboard SELECT logic (read-only by contract). |
| `src/razor_recover/synthetic/` | Synthetic dataset generation and persistence. |
| `src/razor_recover/db/models/` | ORM models: `Transaction`, `Customer`, `Merchant`, `Policy`, `RecoveryDecision`, `RecoveryAttempt`, `AuditLog`. |
| `frontend/` | React 19 + Vite + TypeScript merchant dashboard. |
| `scripts/` | Data generation, ML training, vector-store seeding CLI. |
| `alembic/` | Database migrations (PostgreSQL). |
| `docker/` | `docker-compose.yml` (PostgreSQL 16 + Qdrant local infrastructure). |

---

## Repository structure

```
razorrecover/
├── src/razor_recover/
│   ├── api/v1/endpoints/       # FastAPI route handlers (health, summary, transactions, recovery, audit)
│   ├── workflow/               # RecoveryOrchestrator + port wiring
│   ├── brains/
│   │   ├── ml/                 # Feature builder, risk + recovery models
│   │   ├── rag/                # RAG retrieval, embeddings, vector store, seeding
│   │   └── llm/                # Decision agent + Ollama provider
│   ├── shield/                 # Deterministic policies + 11 rules
│   ├── execution/              # Recovery execution, mock providers
│   ├── tasks/                  # Celery app + async recovery task
│   ├── services/read/          # Dashboard read service (SELECT-only)
│   ├── synthetic/              # Synthetic data generation
│   ├── db/models/              # SQLAlchemy ORM models
│   ├── schemas/                # API request/response models
│   └── core/                   # Database, config
├── frontend/                   # React dashboard (see frontend/README.md)
├── scripts/                    # generate_synthetic_data / train_ml_models / seed_vector_db
├── tests/
│   ├── unit/                   # Feature-level tests (in-memory SQLite)
│   └── integration/            # DB, RAG/Qdrant, dashboard, async + E2E workflow tests
├── alembic/versions/           # Database migrations
├── docker/                     # docker-compose.yml (PostgreSQL + Qdrant)
├── .github/workflows/ci.yml    # CI: backend tests + frontend typecheck/build
├── docs/
│   ├── architecture/           # Architecture deep-dive
│   └── api/                    # HTTP API reference
├── src/razor_recover/config.py # pydantic-settings configuration
└── .env.example                # Environment configuration template
```

---

## Technology stack

| Concern | Choice |
| --- | --- |
| API | FastAPI (Uvicorn) |
| Persistence | PostgreSQL + SQLAlchemy 2 / Alembic |
| Async recovery | Redis (Celery broker + result backend) + Celery |
| ML | scikit-learn (logistic regression, joblib artifacts) |
| Vector store / RAG | Qdrant; hash-based local embeddings (default) or Ollama embeddings |
| LLM | Ollama (local, e.g. `llama3`) behind a provider protocol |
| Policy / shield | Pure-Python deterministic rule engine (no LLM) |
| Execution | Deterministic mocks: `MockPaymentGateway`, `MockNotificationProvider` |
| Frontend | React 19, Vite, TypeScript, react-router |
| Tests | pytest (in-memory SQLite unit tests; PostgreSQL/Qdrant integration tests that skip when unavailable) |

---

## Prerequisites

- Python 3.10+
- Docker (for PostgreSQL and Qdrant)
- Redis (for the optional async path and Celery worker)
- Node.js 18+ (for the frontend)
- Ollama (optional for the LLM; only needed if you want live AI recommendations)

---

## Local setup

A `Makefile` provides convenience wrappers (`make install`, `make test`, `make run`, `make celery`, `make frontend-install`, `make frontend-typecheck`, `make frontend-build`, `make frontend-dev`). The steps below show the equivalent commands.

### 1. Start the infrastructure

```bash
docker compose -f docker/docker-compose.yml up -d
```

This starts PostgreSQL (`localhost:5433`) and Qdrant (`localhost:6333`).

Redis is **not** part of the compose file. For the async/Celery path, run a Redis instance on `localhost:6379`, e.g.:

```bash
docker run -d -p 6379:6379 redis
```

### 2. Backend

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows:  source .venv/bin/activate on Linux/macOS
pip install -r requirements.txt
pip install -e .

cp .env.example .env          # adjust values as needed
alembic upgrade head          # apply database migrations

python scripts/generate_synthetic_data.py   # 20 merchants, 100 customers, 1000 transactions (defaults)
python scripts/train_ml_models.py           # train risk + recovery models (writes models/*.joblib)
python scripts/seed_vector_db.py            # seed the synthetic knowledge base into Qdrant
```

Run the API (from the repository root):

```bash
uvicorn razor_recover.main:app --app-dir src --reload --port 8000
```

Interactive API docs: `http://localhost:8000/docs` (Swagger) and `http://localhost:8000/redoc` (ReDoc) when `DEBUG=true`.

### 3. Async worker (optional)

The synchronous endpoint works without the worker. To also exercise the async path, start a Celery worker (note `--pool=solo` is required on Windows); make sure Redis is running:

```bash
celery -A razor_recover.tasks.celery_app:celery_app worker --pool=solo --loglevel=info
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard runs at `http://localhost:5173` and calls the backend at `http://localhost:8000` by default (override with `VITE_API_BASE_URL`).

---

## API overview

All routes are mounted under `/api/v1`. Full reference: [`docs/api/API.md`](docs/api/API.md).

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Service health |
| `POST` | `/recovery/evaluate` | Run the full recovery workflow for one transaction (sync) |
| `POST` | `/recovery/evaluate/async` | Enqueue the same workflow to a Celery worker (returns a task id) |
| `GET` | `/recovery/tasks/{task_id}` | Poll the state/result of an async task |
| `GET` | `/transactions` | List transactions (filter + paginate) |
| `GET` | `/transactions/{id}` | Full persisted transaction detail |
| `GET` | `/summary` | Dashboard summary metrics (KPIs, decision outcomes, risk/probability buckets, monetary aggregates) |
| `GET` | `/audit` | Paginated audit trail (optionally filtered by transaction) |

All read endpoints (`/transactions`, `/summary`, `/audit`) are read-only by contract — they never execute recovery actions or mutate state. Recovery evaluation fails closed: when an upstream stage (ML/LLM/policy) is unavailable, the request returns `503` and nothing executes.

---

## Testing & verification

```bash
# Backend suite (unit + integration) from the repository root
# (pyproject.toml already puts src/ on the test path)
pytest
```

Current status:

- **241 backend tests passing** (1 upstream deprecation warning: httpx-with-starlette-testclient).
- Unit tests run against in-memory SQLite; integration tests cover PostgreSQL, Qdrant/RAG, the dashboard APIs, and the async/Celery endpoints (they skip automatically when the services are unavailable).
- **Frontend typecheck and production build pass** — `npm run typecheck` is clean and `npm run build` completes successfully.
- Test suites: `tests/unit/` for feature coverage, `tests/integration/` for database, RAG, dashboard, async, and end-to-end workflow tests.
- **CI**: `.github/workflows/ci.yml` runs the backend suite on Python 3.11/3.12 and the frontend typecheck + production build on every push to `main` and on pull requests.

---

## Prototype scope & limitations

This repository is a **working prototype**, built to demonstrate the architecture — not a production system:

- **Synthetic demo data.** Transactions, customers, merchants, and recovery history are generated by `scripts/generate_synthetic_data.py`. There is no real Razorpay customer or payment data anywhere in this repository.
- **Demo policies, not real limits.** Policy thresholds in `.env.example` and the seeded knowledge base are clearly-labeled demo material, not real Razorpay policies.
- **Mock execution providers.** The payment gateway and notification providers are deterministic mocks (`SUCCESS` / `FAILED` / `TIMEOUT`). No real payment system is contacted.
- **Local LLM only.** Decision recommendations come from a local Ollama instance; there is no hosted inference.
- **No authentication.** The dashboard and API have no auth layer; they are intended for local development only.
- **No deployed microservices.** Everything runs as one FastAPI service plus an optional Celery worker on a single machine via Docker.
- **Placeholder scaffolding.** `src/razor_recover/fetchers/*`, `core/redis.py`, and `core/security.py` remain one-line stubs (context fetchers beyond the ORM models, and Windows-only Redis/security wrappers aren't implemented).
- **No deployment target.** A CI workflow (`.github/workflows/ci.yml`) runs the backend tests and frontend typecheck/build, but there is no deployment pipeline, container image, or hosting target — nothing in this repository is deployed anywhere.

Nothing in this project should be used against a live payment gateway.

---

## Disclaimer

All policies, knowledge-base documents, model training data, thresholds, and gateway/notification providers in this repository are synthetic demo material for the RazorRecover prototype. They are not real Razorpay policies, limits, or integrations, and nothing here contacts a real payment system.