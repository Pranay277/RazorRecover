import { Link, useParams } from 'react-router-dom';

import { ApiError } from '@/api';
import { EmptyState, ErrorState, Loading } from '@/components';

import { useTransactionDetail } from './useTransactionDetail';
import { AiAnalysis } from './components/AiAnalysis';
import { AuditTrail } from './components/AuditTrail';
import { DecisionTimeline } from './components/DecisionTimeline';
import { PaymentFailureContext } from './components/PaymentFailureContext';
import { RecoveryHistory } from './components/RecoveryHistory';
import { ShieldDecision } from './components/ShieldDecision';
import { TransactionOverview } from './components/TransactionOverview';

import styles from './index.module.css';

export function TransactionDetails() {
  const rawId = useParams().transactionId ?? '';
  const transactionId = Number(rawId);
  const validId = Number.isInteger(transactionId) && transactionId > 0;

  const { detail, error, loading, reload } = useTransactionDetail(validId ? transactionId : null);

  let body;
  if (!validId) {
    body = (
      <EmptyState
        title="Transaction not found"
        message={`"${rawId}" is not a valid transaction id.`}
      />
    );
  } else if (error) {
    if (error instanceof ApiError && error.status === 404) {
      body = (
        <EmptyState
          title="Transaction not found"
          message={`No transaction with id ${transactionId} exists in the recovery backend.`}
        />
      );
    } else {
      body = (
        <ErrorState
          title="Could not load transaction"
          message="The recovery backend could not be reached while loading this transaction."
          details={error.message}
          onRetry={reload}
        />
      );
    }
  } else if (loading || !detail) {
    body = <Loading label="Loading transaction details…" />;
  } else {
    const latestDecision = detail.decisions.length > 0 ? detail.decisions[0] : null;
    body = (
      <div className={styles.grid}>
        <TransactionOverview transaction={detail} />
        <PaymentFailureContext transaction={detail} />

        <AiAnalysis transaction={detail} latestDecision={latestDecision} />
        <ShieldDecision transaction={detail} latestDecision={latestDecision} />

        <div className={styles.timeline}>
          <DecisionTimeline transaction={detail} latestDecision={latestDecision} />
        </div>

        <RecoveryHistory transaction={detail} />
        <AuditTrail transaction={detail} />
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <Link to="/transactions" className={styles.back}>
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <polyline points="15 18 9 12 15 6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Back to Transactions
      </Link>
      {body}
    </div>
  );
}