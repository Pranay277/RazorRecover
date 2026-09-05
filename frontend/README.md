# RazorRecover Frontend

The RazorRecover merchant dashboard — a **React 19 + Vite + TypeScript** single-page application that lets a merchant see, investigate, and re-evaluate failed payment transactions. It is the read-side UI of the [RazorRecover](..) prototype (ML → RAG → LLM → Shield → Execution → Audit).

## Purpose

The frontend is the merchant-facing view into the recovery decisioning system. It:

- shows **what happened** — recovery outcomes, risk and recovery-probability distributions, and recent failed payments;
- lets a merchant **investigate a failed transaction** — failure context, AI analysis, shield decision, recovery history, audit trail, and decision timeline;
- exposes a **read-only audit trail** of every recovery decision;
- can **enqueue a re-evaluation** for a failed transaction — the frontend only triggers the backend's async workflow and watches its status; it never runs ML, RAG, LLM, policy, or execution logic itself.

## Dashboard screens

| Screen | Route | Description |
| --- | --- | --- |
| Recovery Command Center | `/` | KPI tiles, recovery-outcome chart, risk distribution, recovery-probability buckets, insights panel, recent failed transactions. |
| Transactions Investigation | `/transactions` | Filterable (status, merchant, customer, payment method, gateway, failure code, free-text, date range), paginated transaction list with a summary strip. |
| Transaction Details | `/transactions/:id` | Transaction overview, payment-failure context, AI analysis, shield decision, recovery history, audit trail, decision timeline, and an "Evaluate Recovery" action. |
| Audit Logs | `/audit` | Paginated audit log of recovery decisions, optionally filtered by transaction. |

## Frontend architecture

All components live under `src/`:

```
src/
├── App.tsx                 # Route definitions (React Router)
├── main.tsx                # Entry point (BrowserRouter + global styles)
├── api/                    # Typed backend client
│   ├── client.ts           # fetch transport: API_BASE_URL, error types, request()
│   └── endpoints.ts        # One function per backend endpoint (typed params)
├── components/
│   ├── layout/             # AppLayout, Sidebar, Header, PageContainer
│   └── ui/                 # Card, Table, Button, StatusBadge, Loading, ErrorState, EmptyState
├── hooks/                  # useApiRequest (shared fetch lifecycle)
├── pages/                  # One folder per screen (components + hooks + CSS module)
├── types/                  # Shared TypeScript types (api.ts mirrors backend schemas)
├── styles/                 # tokens.css (design tokens) + global.css
└── utils/                  # format, statusMaps
```

Design decisions:

- **Typed API client.** `src/api/endpoints.ts` maps 1:1 to backend routes and `src/types/api.ts` mirrors the backend response schemas, so a schema change surfaces at compile time.
- **CSS Modules.** Each component ships a co-located `*.module.css` for scoped styling; shared design tokens live in `styles/tokens.css`.
- **Hook-based data access.** Screens delegate fetching/polling to hooks (`useDashboardData`, `useTransactionsData`, `useTransactionDetail`, `useAuditLogsData`, `useEvaluateRecovery`) built on a shared `useApiRequest`.
- **Error-aware transport.** `client.ts` distinguishes network failures (`NetworkError`), non-2xx JSON responses (`ApiError`), and malformed payloads (`JsonError`).

## API dependency

The dashboard is a pure client of the RazorRecover backend (all routes under `/api/v1`). It uses:

| Endpoint | Used by |
| --- | --- |
| `GET /api/v1/summary` | Recovery Command Center |
| `GET /api/v1/transactions` | Transactions Investigation |
| `GET /api/v1/transactions/{id}` | Transaction Details |
| `GET /api/v1/audit` | Audit Logs |
| `POST /api/v1/recovery/evaluate/async` | Transaction Details ("Evaluate Recovery") |
| `GET /api/v1/recovery/tasks/{task_id}` | Transaction Details (status polling) |

See [`../docs/api/API.md`](../docs/api/API.md) for the full backend reference. All read endpoints are read-only by contract; the frontend never mutates or persists state on its own.

## Environment configuration

The only frontend environment variable is `VITE_API_BASE_URL` (default `http://localhost:8000`):

```bash
# frontend/.env (copy from .env.example)
VITE_API_BASE_URL=http://localhost:8000
```

## Local development

The backend must be running first (see the root [README](../README.md#local-setup)). Then:

```bash
cd frontend
npm install
```

Start the dev server (default: `http://localhost:5173`):

```bash
npm run dev
```

## Typecheck & build

```bash
npm run typecheck   # tsc --noEmit -p tsconfig.json
npm run build       # typecheck + Vite production build (dist/)
```

Both pass on the current codebase (`npm run build` typescripts and bundles successfully).