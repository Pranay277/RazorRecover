import { Link } from 'react-router-dom';

import { formatCount, formatMoneyCompact, formatPercent } from '@/utils';
import type { SummaryResponse } from '@/types';

import { humanizeAction, topAction } from '../compute';

import styles from './InsightsPanel.module.css';

interface InsightsPanelProps {
  summary: SummaryResponse;
}

function Row({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className={styles.row}>
      <div className={styles.rowLabel}>{label}</div>
      <div className={styles.rowValue}>{value}</div>
      {sub && <div className={styles.rowSub}>{sub}</div>}
    </div>
  );
}

export function InsightsPanel({ summary }: InsightsPanelProps) {
  const highConfidence = summary.recovery_decisions_by_risk_bucket.low ?? 0;
  const recommended = topAction(summary.recovery_decisions_by_action);
  const manualReview = summary.recovery_decisions_by_outcome.review ?? 0;
  const blocked = summary.recovery_decisions_by_outcome.blocked ?? 0;
  const attemptsTotal = summary.total_recovery_attempts;
  const attemptsRecovered = summary.recovery_attempts_by_status.success ?? 0;

  return (
    <aside className={styles.panel} aria-label="AI Recovery Insights">
      <header className={styles.header}>
        <h2 className={styles.heading}>AI Recovery Insights</h2>
        <p className={styles.caption}>AI recommends · Shield authorizes · Execution runs</p>
      </header>

      <div className={styles.rows}>
        <Row
          label="High-confidence recoveries"
          value={formatCount(highConfidence)}
          sub="Low-risk decisions"
        />
        <Row
          label="Recommended"
          value={recommended ? humanizeAction(recommended.action) : '—'}
          sub={
            recommended
              ? `${formatPercent(recommended.share)} of decisions`
              : 'No recommendations yet'
          }
        />
        <Row label="Requires manual review" value={formatCount(manualReview)} />
        <Row label="Blocked high-risk" value={formatCount(blocked)} />
        <Row
          label="Recovery attempts"
          value={formatCount(attemptsTotal)}
          sub={`${formatCount(attemptsRecovered)} recovered`}
        />
        <Row
          label="Est. Revenue"
          value={formatMoneyCompact(summary.failed_amount)}
          sub="Recoverable amount in failed payments"
        />
      </div>

      <Link className={styles.viewAll} to="/transactions">
        View High-Confidence Recoveries
      </Link>
    </aside>
  );
}