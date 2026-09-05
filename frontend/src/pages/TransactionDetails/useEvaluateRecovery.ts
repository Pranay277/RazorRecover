import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, evaluateRecoveryAsync, getRecoveryTaskStatus, NetworkError } from '@/api';

/**
 * Lifecycle of one manual "Evaluate Recovery" action. The frontend never runs
 * recovery logic - it enqueues the async evaluation, polls the task status,
 * and lets the caller refresh the persisted transaction details on success.
 */
export type EvaluationPhase = 'idle' | 'polling' | 'success' | 'failure' | 'timeout';

/**
 * Sub-progress while polling: the task is either still queued (PENDING) or
 * actually running (STARTED).
 */
export type EvaluationStage = 'queued' | 'running';

export const EVALUATION_POLL_INTERVAL_MS = 1000;
export const EVALUATION_TIMEOUT_MS = 60_000;
export const EVALUATION_SUCCESS_MS = 2500;

interface UseEvaluateRecoveryOptions {
  transactionId: number;
  /** Refresh the transaction detail (called on task SUCCESS). */
  onSuccess?: () => void;
}

interface UseEvaluateRecoveryResult {
  phase: EvaluationPhase;
  stage: EvaluationStage;
  errorMessage: string | null;
  start: () => void;
}

export function useEvaluateRecovery({
  transactionId,
  onSuccess,
}: UseEvaluateRecoveryOptions): UseEvaluateRecoveryResult {
  const [phase, setPhase] = useState<EvaluationPhase>('idle');
  const [stage, setStage] = useState<EvaluationStage>('queued');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const inflightRef = useRef(false);
  const pollTimerRef = useRef<number | null>(null);
  const successTimerRef = useRef<number | null>(null);

  const clearPollTimer = useCallback(() => {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const clearSuccessTimer = useCallback(() => {
    if (successTimerRef.current !== null) {
      window.clearTimeout(successTimerRef.current);
      successTimerRef.current = null;
    }
  }, []);

  // Clean up all timers when the screen unmounts.
  useEffect(
    () => () => {
      clearPollTimer();
      clearSuccessTimer();
    },
    [clearPollTimer, clearSuccessTimer],
  );

  const start = useCallback(() => {
    if (inflightRef.current) {
      return;
    }
    inflightRef.current = true;
    setPhase('polling');
    setStage('queued');
    setErrorMessage(null);

    void (async () => {
      let taskId: string;
      try {
        const accepted = await evaluateRecoveryAsync({ transaction_id: transactionId });
        taskId = accepted.task_id;
      } catch (error) {
        inflightRef.current = false;
        setErrorMessage(toSafeMessage(error, 'Evaluation could not be queued. Please try again.'));
        setPhase('failure');
        return;
      }

      const startedAt = Date.now();
      let inFlightPoll = false;

      const terminate = (terminalPhase: EvaluationPhase, message: string | null) => {
        clearPollTimer();
        inflightRef.current = false;
        setErrorMessage(message);
        setPhase(terminalPhase);
      };

      const tick = () => {
        if (inFlightPoll) {
          return;
        }
        if (Date.now() - startedAt >= EVALUATION_TIMEOUT_MS) {
          terminate('timeout', null);
          return;
        }
        inFlightPoll = true;
        getRecoveryTaskStatus(taskId)
          .then((status) => {
            if (status.status === 'SUCCESS') {
              terminate('success', null);
              onSuccess?.();
              successTimerRef.current = window.setTimeout(
                () => setPhase('idle'),
                EVALUATION_SUCCESS_MS,
              );
            } else if (status.status === 'FAILURE') {
              terminate(
                'failure',
                status.error || 'Evaluation failed. Please try again.',
              );
            } else {
              setStage(status.status === 'STARTED' ? 'running' : 'queued');
            }
          })
          .catch(() => {
            terminate('failure', 'Could not check evaluation status. Please try again.');
          })
          .finally(() => {
            inFlightPoll = false;
          });
      };

      tick();
      if (inflightRef.current) {
        pollTimerRef.current = window.setInterval(tick, EVALUATION_POLL_INTERVAL_MS);
      }
    })();
  }, [transactionId, onSuccess, clearPollTimer]);

  return { phase, stage, errorMessage, start };
}

function toSafeMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return 'This transaction no longer exists in the recovery backend.';
    }
    if (error.status === 422) {
      return 'This transaction cannot be queued for recovery evaluation.';
    }
    return fallback;
  }
  if (error instanceof NetworkError) {
    return error.message;
  }
  return fallback;
}