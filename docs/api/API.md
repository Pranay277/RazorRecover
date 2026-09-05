# RazorRecover API Reference

Base URL: `http://localhost:8000` (all routes mounted under `/api/v1`).

Interactive docs are enabled when `DEBUG=true`:

- Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`

Unless noted, all endpoints are **read-only**: they never execute recovery actions or mutate state.

## Health

### `GET /api/v1/health`

Returns service availability.

```json
{ "status": "ok", "service": "razor-recover" }
```

## Recovery evaluation

### `POST /api/v1/recovery/evaluate`

Runs the full recovery workflow for one transaction: `fetch → ML → RAG → LLM → Shield → Execution → persist → audit`.

Request body:

```json
{ "transaction_id": 42 }
```

Response (`200`):

```json
{
  "transaction_id": 42,
  "risk_score": 0.23,
  "recovery_probability": 0.61,
  "recommended_action": "RETRY_NOW",
  "policy_decision": "ALLOW",
  "authorized_action": "RETRY_NOW",
  "execution_status": "recovered",
  "recovery_status": "recovered",
  "rationale": "…",
  "policy_reasons": ["Risk score within merchant threshold.", "…"],
  "audit_id": 7
}
```

Field semantics:

| Field | Description |
| --- | --- |
| `risk_score` | ML risk score in [0, 1] (probability of loss); `null` if unavailable |
| `recovery_probability` | ML recovery probability in [0, 1]; `null` if unavailable |
| `recommended_action` | The action the LLM requested (`RETRY_NOW`, `DELAYED_RETRY`, `ALTERNATIVE_PAYMENT`, `CUSTOMER_NOTIFICATION`, `MANUAL_REVIEW`, `STOP`) |
| `policy_decision` | `ALLOW` / `BLOCK` / `REVIEW` — the shield's deterministic outcome |
| `authorized_action` | The final action that may run; set only when `ALLOW` |
| `execution_status` | `recovered` / `failed` / `scheduled` / `sent` / `timeout` / `null` (no execution) |
| `recovery_status` | Transaction status after the run |
| `rationale` | LLM rationale |
| `policy_reasons` | Aggregated reasons from failing rules |
| `audit_id` | Id of the persisted audit event |

Error semantics:

- `404` — transaction does not exist.
- `503` — an upstream stage failed (ML models unavailable / LLM unavailable / policy evaluation failed). The request fails closed; nothing executes.

## Asynchronous recovery evaluation (Redis + Celery)

The async path runs the **same** recovery workflow (`fetch → ML → RAG → LLM → Shield → Execution → persist → audit`) in a background Celery worker. It does not re-implement any recovery logic — the task is a thin adapter over the existing orchestrator.

- **Redis role**: two logical databases. `:0` is the Celery **broker** (message/queue transport), `:1` is the Celery **result backend** (task state + serialized results). The API server and worker share the same Redis instance.
- **Celery role**: runs `recovery.evaluate_async` tasks in a worker process, invoking the existing `RecoveryOrchestrator`. Worker failures are recorded as task `FAILURE` (never silently swallowed).

### `POST /api/v1/recovery/evaluate/async`

Enqueues a recovery evaluation and returns immediately with a task id. The workflow is **not** executed inside this endpoint.

Request body:

```json
{ "transaction_id": 42 }
```

Response (`202 Accepted`):

```json
{
  "task_id": "…",
  "status": "queued",
  "transaction_id": 42
}
```

### `GET /api/v1/recovery/tasks/{task_id}`

Polls the state of a queued task. Polling never enqueues another task.

Response (`200`):

```json
{
  "task_id": "…",
  "transaction_id": 42,
  "status": "SUCCESS",
  "result": { "transaction_id": 42, "risk_score": 0.23, "recovery_probability": 0.61, "recommended_action": "RETRY_NOW", "policy_decision": "ALLOW", "authorized_action": "RETRY_NOW", "execution_status": "recovered", "recovery_status": "recovered", "rationale": "…", "policy_reasons": ["…"], "audit_id": 7 },
  "error": null
}
```

`status` is one of:

| Status | Meaning |
| --- | --- |
| `PENDING` | Queued, not started |
| `STARTED` | Worker is executing |
| `SUCCESS` | Workflow completed; `result` holds the serialized evaluation response |
| `FAILURE` | Workflow failed; `error` holds a safe message (never a stack trace) |

`transaction_id` and `result` are `null` unless the task has completed successfully.

### Worker startup (local dev, PowerShell)

Run from the repository root with the `Razor` virtual environment, and ensure `src` is on `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "src"
& .\Razor\Scripts\celery.exe -A razor_recover.tasks.celery_app:celery_app worker --pool=solo --loglevel=info
```

The `--pool=solo` flag is required on Windows (prefork is not supported there). Redis must be running on `localhost:6379` (broker `redis://localhost:6379/0`, result backend `redis://localhost:6379/1`).

## Transactions

### `GET /api/v1/transactions`

Paginated, filterable list of transactions.

Query parameters:

| Param | Type | Description |
| --- | --- | --- |
| `status` | string | Transaction status (e.g. `failed`, `recovered`, `pending`, `abandoned`) |
| `merchant_id` | int | Filter by merchant id (`>= 1`) |
| `customer_id` | int | Filter by customer id (`>= 1`) |
| `payment_method` | string | e.g. `card`, `bank_transfer`, `wallet`, `upi` |
| `gateway` | string | Gateway name |
| `failure_code` | string | Failure category |
| `search` | string | Free-text against external id / customer external id (case-insensitive, 1–128 chars) |
| `attempted_from` | date | Inclusive lower bound on `attempted_at` (`YYYY-MM-DD`) |
| `attempted_to` | date | Inclusive upper bound on `attempted_at` |
| `limit` | int | Default `50`, max `200` |
| `offset` | int | Default `0` |

Response:

```json
{
  "items": [
    {
      "id": 42,
      "external_id": "txn_8492",
      "amount": "129.99",
      "currency": "USD",
      "status": "failed",
      "failure_code": "insufficient_funds",
      "failure_reason": "Account balance below transaction amount",
      "payment_method": "card",
      "gateway": "razorpay",
      "attempt_number": 1,
      "attempted_at": "2026-09-03T10:00:00Z",
      "created_at": "2026-09-03T10:00:00Z",
      "customer_id": 11,
      "merchant_id": 2,
      "customer_external_id": "cus_aa",
      "merchant_external_id": "mrb_01",
      "latest_decision": { "action": "RETRY_NOW", "outcome": "authorized", "risk_score": "0.23", "decided_at": "…" },
      "latest_attempt": { "status": "recovered", "attempt_type": "RETRY_NOW", "started_at": "…", "completed_at": "…" }
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

List rows expose only external customer/merchant references (not names, emails, or phones).

### `GET /api/v1/transactions/{transaction_id}`

Full persisted view of one transaction: merchant, customer, all decisions, all recovery attempts, all audit logs, plus `recovery_probability` and `shield_rule_results` lifted from the most recent evaluate audit event.

- `404` with `{"detail": "Transaction {id} does not exist."}` when the transaction is missing.

## Summary

### `GET /api/v1/summary`

Dashboard metrics computed only from persisted data.

Response fields:

| Field | Description |
| --- | --- |
| `total_transactions` | Count of transactions |
| `transactions_by_status` | `{status → count}` |
| `total_recovery_attempts` | Count of recovery attempts |
| `recovery_attempts_by_status` | `{status → count}` |
| `recovery_decisions_total` | Count of persisted decisions |
| `recovery_decisions_by_outcome` | `{authorized/blocked/review → count}` |
| `recovery_decisions_by_action` | `{action → count}` |
| `recovery_decisions_by_risk_bucket` | `{low/medium/high/unknown → count}` (low < 0.33, medium < 0.66, high ≥ 0.66, unknown = null) |
| `recovery_decisions_by_probability_bucket` | `{0-20/20-40/40-60/60-80/80-100/unknown → count}` over `recovery_probability` for evaluated decisions (aggregated from the persisted `recovery.evaluate:*` audit detail; inclusive lower bound). In the demo dataset there is one evaluated decision per transaction, so the bucket sums to `recovery_decisions_total`. |
| `failed_amount` / `recovered_amount` / `total_amount` | Monetary aggregates as strings (precision preserved) |

## Audit trail

### `GET /api/v1/audit`

Paginated audit log listing, optionally filtered by transaction.

Query parameters:

| Param | Type | Description |
| --- | --- | --- |
| `transaction_id` | int | Filter events for one transaction (`>= 1`) |
| `limit` | int | Default `50`, max `200` |
| `offset` | int | Default `0` |

Response:

```json
{
  "items": [
    {
      "id": 7,
      "transaction_id": 42,
      "transaction_external_id": "txn_8492",
      "actor": "recovery.workflow",
      "action": "recovery.evaluate:ALLOW",
      "detail": { "request_id": "…", "risk_score": 0.23, "recovery_probability": 0.61, "rag_references": ["…"], "llm_requested_action": "RETRY_NOW", "policy_decision": "ALLOW", "policy_version": 1, "rule_results": [ { "rule": "risk_threshold", "passed": true } ], "final_action": "RETRY_NOW", "execution_status": "recovered" },
      "occurred_at": "2026-09-03T10:00:00Z",
      "created_at": "2026-09-03T10:00:00Z",
      "llm_requested_action": "RETRY_NOW",
      "policy_decision": "ALLOW",
      "execution_status": "recovered"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

Events are ordered newest-first. The `detail` object is the raw persisted payload; the trailing first-class fields are convenience views parsed for the UI and are `null` when not applicable.

## General notes

- **Money**: individual amounts serialize as `Decimal` strings in payloads; aggregate sums are strings to avoid floating-point drift.
- **Read-only contract**: `/transactions`, `/summary`, and `/audit` never trigger execution or mutate state (covered by integration tests, e.g. `test_read_endpoints_do_not_mutate_database`).
- **Fail closed**: recovery evaluation returns `503` rather than fabricating a decision when ML/LLM/policy layers are unavailable.
- **Pagination**: all list endpoints paginate via `limit`/`offset` and return `total` for the UI.