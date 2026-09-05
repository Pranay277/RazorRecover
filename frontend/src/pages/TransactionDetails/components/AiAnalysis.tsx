import { formatPercent, humanizeAction } from '@/utils';
import type { RecoveryDecisionRead, TransactionDetail } from '@/types';

import { SectionCard } from './SectionCard';
import { SectionHeading } from './SectionHeading';

import styles from './AiAnalysis.module.css';

interface AiAnalysisProps {
  transaction: TransactionDetail;
  latestDecision: RecoveryDecisionRead | null;
}

function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2.5 14.9 9.1 21.5 12l-6.6 2.9L12 21.5 9.1 14.9 2.5 12l6.6-2.9L12 2.5Z" />
    </svg>
  );
}

interface ScoreProps {
  label: string;
  value: string;
  className?: string;
}

function Score({ label, value, className }: ScoreProps) {
  const classes = [styles.score, className].filter(Boolean).join(' ');
  return (
    <div className={classes}>
      <span className={styles.scoreLabel}>{label}</span>
      <span className={styles.scoreValue}>{value}</span>
    </div>
  );
}

export function AiAnalysis({ transaction, latestDecision }: AiAnalysisProps) {
  const { recovery_probability } = transaction;

  const probability =
    recovery_probability === null || recovery_probability === undefined
      ? '—'
      : formatPercent(recovery_probability * 100);

  const risk = latestDecision?.risk_score ?? null;

  const phaseChip = (
    <span className={styles.suggestionChip}>Suggestion Only</span>
  );

  if (!latestDecision) {
    return (
      <SectionCard
        title={
          <SectionHeading icon={<SparkIcon />} label="AI Recovery Analysis" />
        }
        aside={phaseChip}
      >
        <div className={styles.emptyWrap}>
          <p className={styles.emptyTitle}>No AI evaluation recorded for this transaction.</p>
          <p className={styles.emptyBody}>
            Recovery analysis is produced when the recovery workflow evaluates a failed
            transaction. When a decision exists it appears here as a recommendation only.
          </p>
        </div>
        <div className={styles.scores}>
          <Score label="Recovery Probability" value={probability} />
          <Score label="Risk Score" value="—" className={styles.scoreNeutral} />
        </div>
        <p className={styles.note}>
          * AI suggestions require deterministic policy validation before any scheduling.
        </p>
      </SectionCard>
    );
  }

  return (
    <SectionCard
      title={
        <SectionHeading
          icon={<SparkIcon />}
          label="AI Recovery Analysis"
          sub={formatDecisionTime(latestDecision.decided_at)}
        />
      }
      aside={phaseChip}
    >
      <div className={styles.rec}>
        <span className={styles.recLabel}>Recommended action</span>
        <span className={styles.recValue}>{humanizeAction(latestDecision.action)}</span>
      </div>

      <p className={styles.rationale}>
        {latestDecision.rationale ?? 'This decision has no recorded rationale.'}
      </p>

      <div className={styles.scores}>
        <Score
          label="Recovery Probability"
          value={probability}
          className={recovery_probability === null ? styles.scoreNeutral : styles.scoreSuccess}
        />
        <Score label="Risk Score" value={riskPercentLabel(risk)} className={styles[`risk${riskClass(risk)}`]} />
      </div>

      <p className={styles.note}>
        * AI suggestions require deterministic policy validation before any scheduling.
      </p>
    </SectionCard>
  );
}

function riskPercentLabel(risk: string | number | null | undefined): string {
  if (risk === null || risk === undefined || risk === '') {
    return '—';
  }
  const value = Number(risk);
  if (Number.isNaN(value)) {
    return '—';
  }
  return formatPercent(value * 100);
}

function riskClass(risk: string | number | null | undefined): string {
  if (risk === null || risk === undefined || risk === '') {
    return 'Neutral';
  }
  const value = Number(risk);
  if (Number.isNaN(value)) {
    return 'Neutral';
  }
  if (value < 0.33) {
    return 'Low';
  }
  if (value < 0.66) {
    return 'Medium';
  }
  return 'High';
}

function formatDecisionTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}