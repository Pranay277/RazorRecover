import { useState } from 'react';

import { StatusBadge } from '@/components';
import {
  formatDateTimeCompact,
  formatMoney,
  humanizeLabel,
  transactionStatusBadge,
} from '@/utils';
import type { TransactionDetail } from '@/types';

import { SectionCard } from './SectionCard';

import styles from './TransactionOverview.module.css';

interface TransactionOverviewProps {
  transaction: TransactionDetail;
}

export function TransactionOverview({ transaction }: TransactionOverviewProps) {
  const [copied, setCopied] = useState(false);

  const copyId = async () => {
    try {
      await navigator.clipboard.writeText(transaction.external_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  const method = transaction.payment_method
    ? transaction.gateway
      ? `${humanizeLabel(transaction.payment_method)} (${humanizeLabel(transaction.gateway)})`
      : humanizeLabel(transaction.payment_method)
    : transaction.gateway
      ? humanizeLabel(transaction.gateway)
      : '—';

  return (
    <SectionCard
      footer={
        <>
          <span>
            Created:{' '}
            <span className={styles.footerMono}>
              {formatDateTimeCompact(transaction.created_at)}
            </span>
          </span>
          <span>
            Attempted:{' '}
            <span className={styles.footerMono}>
              {formatDateTimeCompact(transaction.attempted_at)}
            </span>
          </span>
        </>
      }
    >
      <div className={styles.hero}>
        <div className={styles.heroLeft}>
          <span className={styles.heroLabel}>Transaction ID</span>
          <div className={styles.idRow}>
            <span className={styles.txId}>{transaction.external_id}</span>
            <button
              type="button"
              className={styles.copy}
              title="Copy transaction ID"
              aria-label="Copy transaction ID"
              onClick={copyId}
            >
              {copied ? (
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <polyline
                    points="20 6 9 17 4 12"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <rect x="9" y="9" width="13" height="13" rx="2" stroke="currentColor" strokeWidth="1.6" />
                  <path
                    d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
                    stroke="currentColor"
                    strokeWidth="1.6"
                  />
                </svg>
              )}
            </button>
            <StatusBadge {...transactionStatusBadge(transaction.status)} />
          </div>
        </div>
        <div className={styles.heroRight}>
          <span className={styles.heroLabel}>Amount</span>
          <span className={styles.amount}>
            {formatMoney(transaction.amount, transaction.currency)}
          </span>
        </div>
      </div>

      <div className={styles.meta}>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>Customer</span>
          <span className={styles.metaValue}>
            {transaction.customer?.email ?? transaction.customer?.name ?? '—'}
          </span>
        </div>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>Merchant</span>
          <span className={styles.metaValue}>{transaction.merchant?.name ?? '—'}</span>
        </div>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>Payment Method</span>
          <span className={styles.metaValue}>{method}</span>
        </div>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>Attempt Number</span>
          <span className={`${styles.metaValue} ${styles.mono}`}>
            {transaction.attempt_number}
          </span>
        </div>
      </div>
    </SectionCard>
  );
}