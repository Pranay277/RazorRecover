import { Button } from '@/components';
import type { TransactionDetail } from '@/types';

import {
  useEvaluateRecovery,
  type EvaluationPhase,
  type EvaluationStage,
} from '../useEvaluateRecovery';

import styles from './EvaluateRecovery.module.css';

interface EvaluateRecoveryProps {
  transaction: TransactionDetail;
  /** Refresh the transaction details after a successful evaluation. */
  onRefresh: () => void;
}

/**
 * Manual "Evaluate Recovery" action for a failed transaction. This is a pure
 * trigger + status watcher: it enqueues the async evaluation, polls the task,
 * and refreshes the persisted transaction data on success. No recovery logic
 * lives here - the backend keeps owning ML -> RAG -> LLM -> Shield -> Execution
 * -> Audit.
 */
export function EvaluateRecovery({ transaction, onRefresh }: EvaluateRecoveryProps) {
  const hasDecision = transaction.decisions.length > 0;

  const { phase, stage, errorMessage, start } = useEvaluateRecovery({
    transactionId: transaction.id,
    onSuccess: onRefresh,
  });

  if (transaction.status !== 'failed') {
    return null;
  }

  const disabled = phase !== 'idle';

  return (
    <div className={styles.row}>
      <div className={styles.info}>
        <span className={styles.label}>Recovery evaluation</span>
        <span className={`${styles.message} ${messageClass(phase)}`}>
          {statusMessage(phase, stage, hasDecision)}
        </span>
        {errorMessage && <span className={styles.error}>{errorMessage}</span>}
      </div>
      <Button variant="secondary" size="sm" disabled={disabled} onClick={start}>
        {buttonLabel(phase, stage, hasDecision)}
      </Button>
    </div>
  );
}

function buttonLabel(
  phase: EvaluationPhase,
  stage: EvaluationStage,
  hasDecision: boolean,
): string {
  switch (phase) {
    case 'idle':
      return hasDecision ? 'Evaluate Again' : 'Evaluate Recovery';
    case 'polling':
      return stage === 'running' ? 'Evaluating…' : 'Evaluation queued…';
    case 'success':
      return 'Evaluation complete';
    case 'failure':
    case 'timeout':
      return 'Retry Evaluation';
  }
}

function statusMessage(
  phase: EvaluationPhase,
  stage: EvaluationStage,
  hasDecision: boolean,
): string {
  switch (phase) {
    case 'idle':
      return hasDecision
        ? 'Runs a new evaluation and records a new decision for this failed transaction.'
        : 'Runs the full recovery workflow for this failed transaction.';
    case 'polling':
      return stage === 'running' ? 'Evaluating…' : 'Evaluation queued…';
    case 'success':
      return 'Evaluation complete.';
    case 'timeout':
      return 'Evaluation is taking longer than expected.';
    case 'failure':
      return 'Evaluation failed.';
  }
}

function messageClass(phase: EvaluationPhase): string {
  switch (phase) {
    case 'polling':
      return styles.messageActive;
    case 'success':
      return styles.messageSuccess;
    case 'failure':
    case 'timeout':
      return styles.messageError;
    case 'idle':
      return styles.messageIdle;
  }
}