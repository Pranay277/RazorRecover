import { formatDateTimeCompact } from '@/utils';
import type { AuditLogItem, TransactionDetail } from '@/types';

import { SectionCard } from './SectionCard';
import { SectionHeading } from './SectionHeading';

import styles from './AuditTrail.module.css';

interface AuditTrailProps {
  transaction: TransactionDetail;
}

function FileTextIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M6 3.5h9l3.5 3.5v13.5H6V3.5Z" strokeLinejoin="round" />
      <path d="M15 3.5v4h3.5M9 12.5h6M9 16h4" strokeLinecap="round" />
    </svg>
  );
}

const MAX_DETAIL_LENGTH = 200;

function eventClass(action: string, actor: string | null): string {
  const combined = `${action} ${actor ?? ''}`.toLowerCase();
  if (actor === 'recovery.workflow' || combined.includes('recovery')) {
    return styles.eventRecovery;
  }
  if (combined.includes('shield') || combined.includes('policy')) {
    return styles.eventShield;
  }
  if (combined.includes('ai') || combined.includes('llm') || combined.includes('evaluate')) {
    return styles.eventAi;
  }
  return styles.eventSystem;
}

function detailText(detail: Record<string, unknown> | null): string {
  if (detail === null || detail === undefined) {
    return '—';
  }
  try {
    const text = JSON.stringify(detail);
    return text.length > MAX_DETAIL_LENGTH
      ? `${text.slice(0, MAX_DETAIL_LENGTH)}…`
      : text;
  } catch {
    return '—';
  }
}

export function AuditTrail({ transaction }: AuditTrailProps) {
  const logs = transaction.audit_logs;
  const latest = logs.length > 0 ? logs[0] : null;

  return (
    <SectionCard
      title={<SectionHeading icon={<FileTextIcon />} label="Audit Trail" />}
      aside={
        <span className={styles.badge}>
          {logs.length} {logs.length === 1 ? 'event' : 'events'}
        </span>
      }
      footer={
        <span className={styles.footer}>
          {latest
            ? `Latest event at ${formatDateTimeCompact(latest.occurred_at)}`
            : 'No audit events recorded for this transaction'}
        </span>
      }
    >
      {logs.length > 0 ? (
        <div className={styles.terminal}>
          {logs.map((log: AuditLogItem) => (
            <div key={log.id} className={styles.line}>
              <span className={styles.time}>{formatDateTimeCompact(log.occurred_at)}</span>
              <span className={`${styles.actor} ${eventClass(log.action, log.actor)}`}>
                {log.actor ?? 'unknown'}
              </span>
              <span className={styles.action}>{log.action}</span>
              <span className={styles.detail}>{detailText(log.detail)}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className={styles.empty}>
          No audit events were recorded for this transaction. Audit entries appear here as the
          recovery workflow runs.
        </p>
      )}
    </SectionCard>
  );
}