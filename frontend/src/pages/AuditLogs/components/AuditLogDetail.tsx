import { StatusBadge } from '@/components';
import { executionStatusBadge, humanizeAction, shieldBadge } from '@/utils';
import type { AuditLogItem } from '@/types';

import styles from './AuditLogDetail.module.css';

function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

/**
 * Readable inspection of a persisted audit event. Renders the named outline
 * fields (available only when the evaluate event carried them) plus the raw
 * `detail` JSON in a terminal-style block. Nothing is invented.
 */
export function AuditLogDetail({ event }: { event: AuditLogItem }) {
  const aiAction = event.llm_requested_action;
  const policy = event.policy_decision;
  const execution = event.execution_status;
  const detailIsPresent = event.detail !== null && event.detail !== undefined;
  const detailFieldCount = detailIsPresent ? Object.keys(event.detail as object).length : 0;

  return (
    <div className={styles.wrap}>
      <div className={styles.outline}>
        {aiAction ? (
          <div className={styles.outlineItem}>
            <span className={styles.outlineLabel}>Requested AI Action</span>
            <span className={styles.outlineValue}>{humanizeAction(aiAction)}</span>
          </div>
        ) : null}
        {policy ? (
          <div className={styles.outlineItem}>
            <span className={styles.outlineLabel}>Policy Decision</span>
            <StatusBadge {...shieldBadge(policy)} />
          </div>
        ) : null}
        {execution ? (
          <div className={styles.outlineItem}>
            <span className={styles.outlineLabel}>Execution Status</span>
            <StatusBadge {...executionStatusBadge(execution)} />
          </div>
        ) : null}
        {!aiAction && !policy && !execution && (
          <p className={styles.emptyOutline}>
            No decision outline fields were recorded for this event.
          </p>
        )}
      </div>

      <div className={styles.terminal}>
        <div className={styles.terminalBar}>
          <span className={styles.terminalTitle}>event detail</span>
          {detailIsPresent ? (
            <span className={styles.terminalMeta}>
              {detailFieldCount} field{detailFieldCount === 1 ? '' : 's'}
            </span>
          ) : (
            <span className={styles.terminalEmpty}>no detail payload</span>
          )}
        </div>
        {detailIsPresent ? (
          <pre className={styles.terminalCode}>{prettyJson(event.detail)}</pre>
        ) : (
          <p className={styles.terminalEmptyBody}>
            No detail payload was recorded for this event.
          </p>
        )}
      </div>
    </div>
  );
}