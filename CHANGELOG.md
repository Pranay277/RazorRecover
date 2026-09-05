# Changelog

All notable changes to RazorRecover are documented in this file.

## [Unreleased]

### Added
- **Audit Logs frontend screen**: implemented, routed at `/audit`, and backed by the `/api/v1/audit` read API — a paginated, transaction-filterable audit trail of every recovery decision.
- **Asynchronous recovery evaluation**: Redis + Celery path behind `POST /api/v1/recovery/evaluate/async` and `GET /api/v1/recovery/tasks/{task_id}`, with a "Evaluate Recovery" trigger on the transaction detail screen.
- **Aggregate recovery-probability buckets**: `recovery_decisions_by_probability_bucket` on the dashboard summary, aggregated from persisted `recovery.evaluate:*` audit detail.

### Changed
- Frontend shared status maps gained an `executionStatusBadge` mapper for audit/execution payload values.
- Sidebar navigation: "Transaction Details" now routes to `/transactions/{id}` instead of a separate placeholder route.
- CI workflow replaced with a real pipeline that runs the backend test suite and frontend typecheck/build; the placeholder deploy workflow and placeholder `Makefile`/`Dockerfile` scaffolding were removed.

## [0.1.0] - 2026-09-05

Backend vertical slice, read APIs, and merchant dashboard.

### Added
- **Project scaffold**: documented directory structure (`src/`, `docker/`, `scripts/`, `tests/`, `docs/`), CI/deploy workflow placeholders, and local tooling.
- **Database setup**: PostgreSQL persistence with SQLAlchemy ORM models (`Transaction`, `Customer`, `Merchant`, `Policy`, `RecoveryDecision`, `RecoveryAttempt`, `AuditLog`) and Alembic migrations (`initial schema`, `add transaction payment fields`).
- **Synthetic payment data pipeline**: seeded, reproducible generation of merchants, customers, and failed transactions with realistic failure categories, plus CLI persistence (`scripts/generate_synthetic_data.py`).
- **ML risk and recovery models**: explicit no-leakage feature builder, scikit-learn logistic-regression risk and recovery models, training/evaluation flow with metrics, and joblib artifact save/load (`scripts/train_ml_models.py`).
- **RAG knowledge base and retrieval**: Qdrant-backed vector store, pluggable embeddings (deterministic local hash; optional Ollama), retriever with merchant scoping, synthetic demo knowledge base, and seeding CLI (`scripts/seed_vector_db.py`).
- **AI decision agent**: Ollama-backed LLM provider abstraction, system/user prompts, strict JSON extraction and Pydantic validation into an `AgentDecision` recommendation from a fixed `AllowedAction` set.
- **Policy and safety engine**: deterministic shield with 11 composable rules, fail-closed rule aggregation yielding `ALLOW` / `REVIEW` / `BLOCK`, per-merchant policy support, and auditable `PolicyDecision` output.
- **End-to-end recovery workflow**: `RecoveryOrchestrator` pipeline `fetch → ML → RAG → LLM → Policy → Execution → persist → audit`, with mock payment gateway and notification providers, execution idempotency/in-flight guards, and fail-closed stage handling (`src/razor_recover/workflow/`).
- **Dashboard read APIs**: read-only transaction listing (filters, search, pagination), transaction detail with nested persisted records, summary metrics, and audit trail endpoint (`src/razor_recover/services/read/`).
- **Frontend foundation and dashboard API contracts**: React 19 + Vite + TypeScript app, typed API client/endpoints, shared UI components, and app layout with sidebar navigation.
- **Recovery Command Center**: KPI cards, recovery-outcome chart, risk distribution, recovery-probability view, insights panel, and recent-failed payments table backed by the summary/read APIs.
- **Transactions Investigation**: filterable, paginated failed-transaction table with summary strip.
- **Transaction Details**: overview, payment-failure context, AI analysis, shield decision, recovery history, audit trail, and decision timeline from the persisted transaction detail API.
- **Tests**: unit coverage for synthetic generation/persistence, ML features/models, RAG, LLM agent, shield/policy engine, execution, database, and models; integration coverage for the evaluation workflow, dashboard/audit APIs, PostgreSQL schema/alembic head, Qdrant RAG, and an optional live-Ollama agent test.

### Changed
- Root endpoints exposed under `/api/v1` with a FastAPI application factory, typed settings (`pydantic-settings`), and a dependency-injected composition root.