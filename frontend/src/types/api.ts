/**
 * API types mirroring the RazorRecover backend schemas exactly.
 *
 * Source of truth: src/razor_recover/schemas/dashboard.py and
 * src/razor_recover/workflow/schemas.py. Do not invent fields here - if a
 * field is absent from this file, the backend does not expose it.
 *
 * Money is serialized by the backend as string (Decimal to preserve
 * precision). Timestamps are ISO-8601 strings.
 */

/** Most recent recovery decision attached to a list row. */
export interface RecoveryDecisionSummary {
  action: string;
  outcome: string;
  risk_score: string | null;
  rationale: string | null;
  decided_at: string;
}

/** Most recent recovery attempt attached to a list row. */
export interface RecoveryAttemptSummary {
  status: string;
  attempt_type: string;
  error_detail: string | null;
  started_at: string | null;
  completed_at: string | null;
}

/** One row of the transactions list. */
export interface TransactionListItem {
  id: number;
  external_id: string;
  amount: string;
  currency: string;
  status: string;
  failure_code: string | null;
  failure_reason: string | null;
  payment_method: string | null;
  gateway: string | null;
  attempt_number: number;
  attempted_at: string | null;
  created_at: string;
  customer_id: number;
  merchant_id: number;
  customer_external_id: string | null;
  merchant_external_id: string | null;
  latest_decision: RecoveryDecisionSummary | null;
  latest_attempt: RecoveryAttemptSummary | null;
}

export interface TransactionListResponse {
  items: TransactionListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface CustomerReference {
  id: number;
  external_id: string;
  name: string;
  email: string | null;
  status: string;
}

export interface MerchantReference {
  id: number;
  external_id: string;
  name: string;
  industry: string | null;
  status: string;
}

export interface RecoveryDecisionRead {
  id: number;
  transaction_id: number;
  action: string;
  outcome: string;
  risk_score: string | null;
  policy_version: number | null;
  rationale: string | null;
  decided_at: string;
  created_at: string;
}

export interface RecoveryAttemptRead {
  id: number;
  transaction_id: number;
  decision_id: number | null;
  status: string;
  attempt_type: string;
  error_detail: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ShieldRuleResult {
  rule: string;
  passed: boolean;
  disposition: string | null;
}

export interface AuditLogItem {
  id: number;
  transaction_id: number | null;
  transaction_external_id: string | null;
  actor: string | null;
  action: string;
  detail: Record<string, unknown> | null;
  occurred_at: string;
  created_at: string;
  llm_requested_action: string | null;
  policy_decision: string | null;
  execution_status: string | null;
}

export interface TransactionDetail extends TransactionListItem {
  customer: CustomerReference | null;
  merchant: MerchantReference | null;
  decisions: RecoveryDecisionRead[];
  attempts: RecoveryAttemptRead[];
  audit_logs: AuditLogItem[];
  recovery_probability: number | null;
  shield_rule_results: ShieldRuleResult[] | null;
}

export interface SummaryResponse {
  total_transactions: number;
  transactions_by_status: Record<string, number>;
  total_recovery_attempts: number;
  recovery_attempts_by_status: Record<string, number>;
  recovery_decisions_total: number;
  recovery_decisions_by_outcome: Record<string, number>;
  recovery_decisions_by_action: Record<string, number>;
  recovery_decisions_by_risk_bucket: Record<string, number>;
  recovery_decisions_by_probability_bucket: Record<string, number>;
  failed_amount: string;
  recovered_amount: string;
  total_amount: string;
}

export interface AuditListResponse {
  items: AuditLogItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface EvaluateResponse {
  transaction_id: number;
  risk_score: number | null;
  recovery_probability: number | null;
  recommended_action: string | null;
  policy_decision: string;
  authorized_action: string | null;
  execution_status: string | null;
  recovery_status: string | null;
  rationale: string | null;
  policy_reasons: string[];
  audit_id: number | null;
}

export interface EvaluateRequest {
  transaction_id: number;
}

/** Immediate response when an evaluation is enqueued for async processing. */
export interface RecoveryTaskAccepted {
  task_id: string;
  status: string;
  transaction_id: number;
}

/**
 * States reported by GET /api/v1/recovery/tasks/{task_id}. The backend
 * normalizes Celery states to exactly these four values.
 */
export type RecoveryTaskState = 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE';

/** Stable view of one asynchronous recovery task. */
export interface RecoveryTaskStatus {
  task_id: string;
  transaction_id: number | null;
  status: RecoveryTaskState;
  result: EvaluateResponse | null;
  error: string | null;
}