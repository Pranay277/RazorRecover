import { StatusBadge, Table, TBody, TCell, THead, THeadCell, TRow } from '@/components';
import { attemptBadge, formatDateTimeCompact, humanizeLabel } from '@/utils';
import type { TransactionDetail } from '@/types';

import { SectionCard } from './SectionCard';
import { SectionHeading } from './SectionHeading';

import styles from './RecoveryHistory.module.css';

interface RecoveryHistoryProps {
  transaction: TransactionDetail;
}

function HistoryIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M3.5 9a9 9 0 1 1 2 5.5" strokeLinecap="round" />
      <polyline points="12 7 12 12 15.5 14" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function RecoveryHistory({ transaction }: RecoveryHistoryProps) {
  const attempts = [...transaction.attempts].reverse();
  const latest = transaction.attempts.length > 0 ? transaction.attempts[0] : null;

  return (
    <SectionCard
      title={<SectionHeading icon={<HistoryIcon />} label="Recovery History" />}
      aside={
        <span className={styles.count}>
          {transaction.attempts.length} recorded{' '}
          {transaction.attempts.length === 1 ? 'attempt' : 'attempts'}
        </span>
      }
      footer={
        <span className={styles.footer}>
          {latest
            ? `Latest resolved at ${formatDateTimeCompact(latest.completed_at ?? latest.started_at)}`
            : 'No recovery attempts recorded'}
        </span>
      }
    >
      {attempts.length > 0 ? (
        <Table>
          <THead>
            <tr>
              <THeadCell>Attempt</THeadCell>
              <THeadCell>Type</THeadCell>
              <THeadCell>Status</THeadCell>
              <THeadCell align="right">Decision</THeadCell>
              <THeadCell>Started</THeadCell>
              <THeadCell>Completed</THeadCell>
              <THeadCell>Error</THeadCell>
            </tr>
          </THead>
          <TBody>
            {attempts.map((attempt) => (
              <TRow key={attempt.id}>
                <TCell mono>#{attempt.id}</TCell>
                <TCell>{humanizeLabel(attempt.attempt_type)}</TCell>
                <TCell>
                  <StatusBadge {...attemptBadge(attempt.status)} />
                </TCell>
                <TCell align="right" mono>
                  {attempt.decision_id ? `#${attempt.decision_id}` : '—'}
                </TCell>
                <TCell mono>{formatDateTimeCompact(attempt.started_at)}</TCell>
                <TCell mono>{formatDateTimeCompact(attempt.completed_at)}</TCell>
                <TCell className={styles.errorCell}>
                  {attempt.error_detail ?? '—'}
                </TCell>
              </TRow>
            ))}
          </TBody>
        </Table>
      ) : (
        <p className={styles.empty}>
          No recovery attempts were recorded for this transaction. Attempts appear here once the
          recovery plan is executed.
        </p>
      )}
    </SectionCard>
  );
}