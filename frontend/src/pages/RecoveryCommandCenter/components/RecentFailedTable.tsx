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
import { formatMoney } from '@/utils';
import type { TransactionListItem } from '@/types';

import { attemptBadge, humanizeAction, riskBadge, shieldBadge } from '../compute';

import styles from './RecentFailedTable.module.css';

interface RecentFailedTableProps {
  items: TransactionListItem[];
}

export function RecentFailedTable({ items }: RecentFailedTableProps) {
  const navigate = useNavigate();

  if (items.length === 0) {
    return <p className={styles.empty}>No failed payments found.</p>;
  }

  return (
    <Table>
      <THead>
        <TRow>
          <THeadCell>Transaction</THeadCell>
          <THeadCell>Customer</THeadCell>
          <THeadCell align="right">Amount</THeadCell>
          <THeadCell>Failure Reason</THeadCell>
          <THeadCell>Risk</THeadCell>
          <THeadCell>AI Recommendation</THeadCell>
          <THeadCell>Shield</THeadCell>
          <THeadCell>Status</THeadCell>
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
                    {transaction.payment_method ?? transaction.gateway ?? '—'}
                  </span>
                </div>
              </TCell>
              <TCell mono>{transaction.customer_external_id ?? '—'}</TCell>
              <TCell align="right" mono>
                {formatMoney(transaction.amount, transaction.currency)}
              </TCell>
              <TCell className={styles.reasonColumn}>
                {transaction.failure_reason ?? '—'}
              </TCell>
              <TCell>
                <StatusBadge {...riskBadge(transaction.latest_decision?.risk_score)} />
              </TCell>
              <TCell>
                <span className={recoClasses}>{humanizeAction(action)}</span>
              </TCell>
              <TCell>
                <StatusBadge {...shieldBadge(transaction.latest_decision?.outcome)} />
              </TCell>
              <TCell>
                <StatusBadge {...attemptBadge(transaction.latest_attempt?.status)} />
              </TCell>
            </TRow>
          );
        })}
      </TBody>
    </Table>
  );
}