import { useNavigate } from 'react-router-dom';

import {
  StatusBadge,
  Table,
  TBody,
  TCell,
  THead,
  THeadCell,
  TRow,
} from '@/components';
import {
  formatDateTimeCompact,
  formatMoney,
  humanizeAction,
  shieldBadge,
  transactionStatusBadge,
} from '@/utils';
import type { TransactionListItem } from '@/types';

import styles from './TransactionsTable.module.css';

interface TransactionsTableProps {
  items: TransactionListItem[];
}

export function TransactionsTable({ items }: TransactionsTableProps) {
  const navigate = useNavigate();

  return (
    <Table>
      <THead>
        <TRow>
          <THeadCell>Transaction</THeadCell>
          <THeadCell>Customer</THeadCell>
          <THeadCell align="right">Amount</THeadCell>
          <THeadCell>Status</THeadCell>
          <THeadCell>AI Recommendation</THeadCell>
          <THeadCell>Shield Decision</THeadCell>
          <THeadCell>Gateway</THeadCell>
          <THeadCell>Attempted</THeadCell>
          <THeadCell className={styles.chevronHead} aria-hidden="true" />
        </TRow>
      </THead>
      <TBody>
        {items.map((transaction) => {
          const action = transaction.latest_decision?.action ?? '';
          const recoClasses = [styles.reco, !action && styles.recoNone]
            .filter(Boolean)
            .join(' ');
          return (
            <TRow
              key={transaction.id}
              onClick={() => navigate(`/transactions/${transaction.id}`)}
            >
              <TCell>
                <div className={styles.txGroup}>
                  <span className={styles.txId}>{transaction.external_id}</span>
                  <span className={styles.txMeta}>
                    {transaction.failure_code ?? '—'}
                  </span>
                </div>
              </TCell>
              <TCell mono>{transaction.customer_external_id ?? '—'}</TCell>
              <TCell align="right" mono>
                {formatMoney(transaction.amount, transaction.currency)}
              </TCell>
              <TCell>
                <StatusBadge {...transactionStatusBadge(transaction.status)} />
              </TCell>
              <TCell>
                <span className={recoClasses}>{humanizeAction(action)}</span>
              </TCell>
              <TCell>
                <StatusBadge {...shieldBadge(transaction.latest_decision?.outcome)} />
              </TCell>
              <TCell>{transaction.gateway ?? '—'}</TCell>
              <TCell mono>{formatDateTimeCompact(transaction.attempted_at)}</TCell>
              <TCell className={styles.chevronCell}>
                <svg
                  className={styles.chevron}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="m9 18 6-6-6-6" />
                </svg>
              </TCell>
            </TRow>
          );
        })}
      </TBody>
    </Table>
  );
}