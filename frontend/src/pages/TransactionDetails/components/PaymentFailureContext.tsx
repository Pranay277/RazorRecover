import { humanizeLabel } from '@/utils';
import type { TransactionDetail } from '@/types';

import { SectionCard } from './SectionCard';
import { SectionHeading } from './SectionHeading';

import styles from './PaymentFailureContext.module.css';

interface PaymentFailureContextProps {
  transaction: TransactionDetail;
}

function AlertIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M12 9v4M12 16.5h.01" strokeLinecap="round" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" />
      <polyline points="8.5 12 11 14.5 15.5 10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function PaymentFailureContext({ transaction }: PaymentFailureContextProps) {
  const isFailed = transaction.status === 'failed';
  const status = transactionStatusLabel(transaction.status);
  const hasCode = Boolean(transaction.failure_code);
  const hasReason = Boolean(transaction.failure_reason);

  return (
    <SectionCard
      title={
        <SectionHeading icon={<AlertIcon />} label="Payment Failure Context" />
      }
      footer={
        <span className={styles.footer}>
          Payment attempted on{' '}
          <span className={styles.footerMono}>
            {transaction.attempted_at ?? '—'}
          </span>{' '}
          · Attempt #{transaction.attempt_number}
        </span>
      }
    >
      <div className={styles.lead}>
        <span className={styles.leadStatus}>{status}</span>
        <span className={styles.leadText}>
          {isFailed
            ? 'The payment attempt failed and the transaction is now eligible for recovery review.'
            : 'This transaction is not in a failed state, so no payment failure context applies.'}
        </span>
      </div>

      {isFailed && (hasCode || hasReason) ? (
        <dl className={styles.grid}>
          {hasCode && (
            <div className={styles.item}>
              <dt className={styles.label}>Failure Code</dt>
              <dd className={`${styles.value} ${styles.mono}`}>{transaction.failure_code}</dd>
            </div>
          )}
          {hasReason && (
            <div className={styles.item}>
              <dt className={styles.label}>Reason</dt>
              <dd className={styles.value}>{transaction.failure_reason}</dd>
            </div>
          )}
        </dl>
      ) : isFailed ? (
        <p className={styles.empty}>
          No declared failure code or reason was recorded from the payment gateway.
        </p>
      ) : (
        <div className={styles.honest}>
          <span className={styles.honestIcon} aria-hidden="true">
            <CheckIcon />
          </span>
          <span>No payment failure was recorded for this transaction.</span>
        </div>
      )}
    </SectionCard>
  );
}

function transactionStatusLabel(status: string | null | undefined): string {
  if (!status) {
    return 'Unknown status';
  }
  return humanizeLabel(status);
}