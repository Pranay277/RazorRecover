# RazorRecover Architecture

RazorRecover is a **risk-aware, constrained revenue-recovery decisioning system** for failed payment transactions. This document describes the system as built in this repository.

## 1. Core principle

```
AI / LLM Agent recommends
            ↓
Deterministic Policy Engine authorizes
            ↓
Execution Layer performs
```

The LLM never executes anything. Its output is a **recommendation** consumed by a deterministic policy engine that decides `ALLOW` / `REVIEW` / `BLOCK`. Only an `ALLOW` decision causes the execution layer to act, and the whole trail is persisted and surfaced through read-only dashboard APIs.

Every component honors fail-closed behavior: missing context, model unavailability, or an unexpected error can prevent execution but can never accidentally authorize it.

## 2. Request lifecycle

The API surface is intentionally thin. Business logic lives in the **`RecoveryOrchestrator`** pipeline:

```
1. fetch transaction        workflow/orchestrator.py  (_fetch_transaction)
2. ML prediction            brains/ml/service.py        → risk_score, recovery_probability
3. RAG retrieval            brains/rag/service.py       → top-k merchant-scoped policy context (best effort)
4. LLM decision             brains/llm/agent.py         → AgentDecision (validated recommendation)
5. Policy authorization     shield/policy_engine.py     → PolicyDecision (ALLOW / REVIEW / BLOCK)
6. Execution                execution/recovery_service.py  → RecoveryAttempt (only on ALLOW)
7. Persist decision         ␊                              → RecoveryDecision row
8. Audit                    ␊                              → AuditLog row
9. Respond                  ␊                              → EvaluateResponse
```

Stage boundaries are wired as injection **ports** (`workflow/ports.py`), so each layer can be swapped or faked in tests without touching the orchestrator.

### Pipeline detail

**ML stage.** The transaction (plus customer transaction history) is mapped into a feature vector (`workflow/context.py` builds a `FeatureSource`; `brains/ml/features.py` encodes it). Two logistic-regression models, loaded lazily from `models/risk_model.joblib` and `models/recovery_model.joblib` (`brains/ml/model_base.py`), emit `risk_score` and `recovery_probability`, both in [0, 1]. The feature set is explicit and audited against **target leakage**: `status`, `attempt_number`, decision fields, and recovery attempts are deliberately excluded. If the artifacts are missing, the stage raises `MLStageError` and the request fails closed.

**RAG stage.** On a best-effort basis, the failure code/reason is used to query a Qdrant-backed knowledge base scoped to the transaction's merchant (`brains/rag/`). Failure is **not** fatal — missing retrieval yields empty context (`RAGService` may return `None`). All knowledge is synthetic demo material carrying an explicit disclaimer.

**LLM stage.** The agent (`brains/llm/agent.py`) receives the transaction, customer, and merchant snapshots plus ML scores and RAG context, and must return a **structurally validated JSON recommendation** choosing from `AllowedAction`:

```
RETRY_NOW | DELAYED_RETRY | ALTERNATIVE_PAYMENT | CUSTOMER_NOTIFICATION | MANUAL_REVIEW | STOP
```

Output is parsed tolerantly (`extract_json`) but validated strictly (Pydantic `AgentDecision`), so malformed producer output throws `InvalidDecisionError` instead of propagating. Provider errors raise `LLMError` and fail the stage; the system never fabricates a decision. The default provider is Ollama (`brains/llm/providers.py`), behind a protocol so it can be swapped.

**Shield stage.** The policy engine (`shield/policy_engine.py`) evaluates the recommendation against `EvaluationContext` — the requested action, transaction snapshot, merchant policy, ML scores, and retry history — using **no LLM involvement**. It runs 11 deterministic rules (`shield/rules.py`):

1. `action_allowlist` — reject missing/unparseable actions
2. `stop_action` — `STOP` always blocks
3. `manual_review_action` — `MANUAL_REVIEW` always escalates (never `ALLOW`)
4. `transaction_presence` — fail closed if transaction missing
5. `merchant_policy_availability` — policy-dependent actions fail closed without policy
6. `merchant_restriction` — block actions a merchant explicitly disallows
7. `retry_guards` — retries disabled → block; no retry history → review; attempt limit reached → block
8. `risk_threshold` — retries above the merchant risk threshold → block; alternative payment above it → review
9. `recovery_probability` — below the minimum → review (low confidence)
10. `high_value_review` — high-value transactions escalate to review
11. `customer_notification` — respect communication restrictions

Aggregation is deterministic and fail-closed (`shield/evaluator.py`): any `BLOCK` → `BLOCK`; else any `REVIEW` → `REVIEW`; else `ALLOW`. A rule that raises is recorded as a `BLOCK`. The resulting `PolicyDecision` carries per-rule results, aggregated reasons, policy version, and timestamps.

**Execution stage.** `RecoveryService` (`execution/recovery_service.py`) is the only component that performs actions, and it **independently verifies** that the decision is `ALLOW` with a non-empty `final_action` before doing so — an arbitrary LLM action is never trusted. It guards against duplicate in-flight attempts and maps actions to gateway/notification providers:

- `RETRY_NOW` → mock gateway charge (`SUCCESS` / `FAILED` / `TIMEOUT`)
- `DELAYED_RETRY` → recorded as `scheduled` (no immediate gateway call)
- `ALTERNATIVE_PAYMENT` → mock gateway charge via an alternative method
- `CUSTOMER_NOTIFICATION` → mock notification provider
- `MANUAL_REVIEW` / `STOP` → never auto-executed (raises)

A successful recovery transaction is marked `recovered`. Execution results (`recovered` / `failed` / `scheduled` / `sent` / `timeout`) are persisted on the `RecoveryAttempt`.

**Audit stage.** Each evaluation appends an `AuditLog` row whose `detail` JSON captures the request id, ML scores, RAG document references, the LLM requested action and rationale, the policy decision/version and reasons, every rule result, and the final execution status/message.

## 3. Safety model

- The LLM is advisory only; the shield is deterministic and does not consult the LLM.
- Missing required data fails closed (missing risk score, recovery probability, or retry history → `REVIEW`; missing merchant policy for policy-dependent actions → `REVIEW`; unknown/degenerate actions → `BLOCK`).
- Any rule or engine exception results in `BLOCK`.
- The execution layer refuses to run anything other than an `ALLOW` decision and re-verifies the `final_action` before dispatching.
- `MANUAL_REVIEW` can never be auto-executed; `STOP` always blocks.

## 4. Read / dashboard side

`DashboardReadService` (`services/read/dashboard.py`) is the single owner of all SELECT logic and is **read-only by contract**: it never executes, mutates, or recomputes ML/RAG/LLM at request time. It serializes rows already persisted by the workflow:

- `list_transactions` — paginated, filterable (status, merchant, customer, payment method, gateway, failure code, free-text search on external/customer id, date range), enriched with latest decision/attempt summaries.
- `get_transaction_detail` — a transaction with nested merchant, customer, decisions, attempts, audit logs, plus `recovery_probability` and shield rule results lifted from the newest evaluate audit event.
- `get_summary` — counts by transaction status, attempt status, decision outcome/action, risk buckets, and monetary aggregates.
- `list_audit_logs` — paginated audit trail, optionally filtered by `transaction_id`, with first-class views (`llm_requested_action`, `policy_decision`, `execution_status`) parsed from the persisted payloads.

Schema-level privacy: list payloads expose only external customer/merchant ids; sensitive fields (emails, phones) appear only on the detail read model.

## 5. Data model

```
merchants ─┬─< transactions >─┬─ customers
           │
policies <─┘
transactions >─ recovery_decisions >─ recovery_attempts
transactions >─ audit_logs
```

- `transactions` — failed payment (unique `external_id`, amount/currency, status, failure code/reason, payment method, gateway, attempt number).
- `customers`, `merchants` — parties; `merchants` have an `industry` used by the ML feature builder.
- `policies` — stored deterministic policy definitions (priority, enablement, expression).
- `recovery_decisions` — outcome of one evaluation (requested action, `authorized`/`blocked`/`review`, risk score, policy version, rationale).
- `recovery_attempts` — one performed action (status, type, error detail, start/complete timestamps).
- `audit_logs` — immutable event log (actor, action, JSON detail, occurred_at).

Migrations live in `alembic/versions/` (PostgreSQL). Run: `alembic upgrade head`.

## 6. Frontend

A React 19 + Vite + TypeScript SPA (`frontend/`) consumes the read APIs through a typed client (`src/api/`). Current screens:

- **Recovery Command Center** (`/`) — KPIs, recovery-outcome chart, risk distribution, recovery-probability, insights, recent failed payments.
- **Transactions Investigation** (`/transactions`) — filterable, paginated table with summary strip.
- **Transaction Details** (`/transactions/:id`) — overview, failure context, AI analysis, shield decision, recovery history, audit trail, decision timeline.
- **Audit Logs** (`/audit`) — **in progress**: data hook and filter constants exist; the routed screen is pending (backend API is complete).

The frontend reads persisted data only; it never triggers recovery or mutates state.

## 7. Runtime & configuration

- **Settings**: `src/razor_recover/config.py` (pydantic-settings), loaded from environment vars or `.env` (see `.env.example`).
- **Infrastructure** (via `docker/docker-compose.yml`): PostgreSQL 16 (`localhost:5433`) and Qdrant (`localhost:6333`).
- **Scripts** (`scripts/`): `generate_synthetic_data.py`, `train_ml_models.py`, `seed_vector_db.py`.
- Placeholder scaffolding that this repository does **not** yet implement: `fetchers/*` (context fetchers beyond DB models), `core/redis.py`, `core/security.py`, a production Dockerfile, and real CI/deploy workflows (`Makefile` and `.github/workflows/` remain placeholders).

## 8. Technology choices

| Concern | Choice |
| --- | --- |
| API | FastAPI (Uvicorn) |
| Persistence | PostgreSQL + SQLAlchemy 2 / Alembic |
| ML | scikit-learn (logistic regression, explicit features, joblib artifacts) |
| Vector store / RAG | Qdrant; hash-based local embeddings (default) or Ollama embeddings |
| LLM | Ollama (llama3) behind a provider protocol |
| Policy / shield | Pure Python deterministic rule engine (no LLM) |
| Execution | Deterministic mocks: `MockPaymentGateway`, `MockNotificationProvider` |
| Frontend | React 19, Vite, TypeScript, react-router |
| Tests | pytest (in-memory SQLite unit tests; PostgreSQL/Qdrant integration tests that skip when unavailable) |