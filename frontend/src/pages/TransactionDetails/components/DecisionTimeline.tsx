import { attemptBadge, shieldBadge, transactionStatusBadge } from '@/utils';
import type { RecoveryAttemptRead, RecoveryDecisionRead, TransactionDetail } from '@/types';

import { SectionCard } from './SectionCard';
import { SectionHeading } from './SectionHeading';

import styles from './DecisionTimeline.module.css';

interface DecisionTimelineProps {
  transaction: TransactionDetail;
  latestDecision: RecoveryDecisionRead | null;
}

interface TimelineNode {
  label: string;
  time: string;
  note: string;
  toneClass: string;
  muted: boolean;
}

function ClockIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" />
      <polyline points="12 7.5 12 12 15 14" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function decisionTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${pad(date.getFullYear())}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

function buildNodes(
  transaction: TransactionDetail,
  latestDecision: RecoveryDecisionRead | null,
): TimelineNode[] {
  const statusBadge = transactionStatusBadge(transaction.status);
  const isFailed = transaction.status === 'failed';
  const decisionTimeValue = latestDecision ? decisionTime(latestDecision.decided_at) : '—';

  const attempt =
    transaction.attempts.length > 0 ? transaction.attempts[0] : null;

  return [
    {
      label: 'Payment failed',
      time: transaction.attempted_at ?? transaction.created_at,
      note: isFailed ? 'Eligible for recovery review' : `Transaction status: ${statusBadge.label}`,
      toneClass: isFailed ? styles.toneDanger : styles.toneNeutral,
      muted: !isFailed,
    },
    {
      label: 'AI context & analysis',
      time: latestDecision ? decisionTimeValue : '—',
      note: latestDecision
        ? `Machine-learning analysis — persisted with decision #${latestDecision.id}`
        : 'Not recorded',
      toneClass: latestDecision ? styles.toneInfo : styles.toneNeutral,
      muted: !latestDecision,
    },
    {
      label: 'Shield policy check',
      time: latestDecision ? decisionTimeValue : '—',
      note: latestDecision
        ? `Deterministic validation · outcome ${shieldBadge(latestDecision.outcome).label}`
        : 'Not recorded',
      toneClass: latestDecision
        ? toneForOutcome(shieldBadge(latestDecision.outcome).tone)
        : styles.toneNeutral,
      muted: !latestDecision,
    },
    {
      label: 'Recovery',
      time: attempt
        ? (attempt.completed_at ?? attempt.started_at ?? attempt.created_at)
        : '—',
      note: attempt
        ? `Attempt #${attempt.id} · ${attemptBadge(attempt.status).label}`
        : latestDecision
          ? 'Awaiting execution'
          : 'Not scheduled',
      toneClass: attempt ? toneForAttempt(attempt) : styles.toneNeutral,
      muted: !attempt,
    },
  ];
}

function toneForOutcome(tone: string): string {
  switch (tone) {
    case 'success':
      return styles.toneSuccess;
    case 'warning':
      return styles.toneWarning;
    case 'danger':
      return styles.toneDanger;
    default:
      return styles.toneInfo;
  }
}

function toneForAttempt(attempt: RecoveryAttemptRead): string {
  switch (attempt.status) {
    case 'recovered':
    case 'success':
      return styles.toneSuccess;
    case 'scheduled':
    case 'running':
    case 'sent':
      return styles.toneInfo;
    case 'timeout':
      return styles.toneWarning;
    case 'failed':
      return styles.toneDanger;
    default:
      return styles.toneNeutral;
  }
}

export function DecisionTimeline({ transaction, latestDecision }: DecisionTimelineProps) {
  const nodes = buildNodes(transaction, latestDecision);

  return (
    <SectionCard
      title={<SectionHeading icon={<ClockIcon />} label="Decision Timeline & Orchestration" />}
      aside={<span className={styles.legend}>Read-only live view · times from persisted rows</span>}
    >
      <ol className={styles.track}>
        {nodes.map((node) => (
          <li
            key={node.label}
            className={`${styles.node} ${node.muted ? styles.muted : ''}`}
          >
            <span className={styles.nodeHead}>
              <span className={`${styles.dot} ${node.toneClass}`} aria-hidden="true" />
              <span className={styles.label}>{node.label}</span>
            </span>
            <span className={styles.time}>{node.time}</span>
            <span className={styles.note}>{node.note}</span>
          </li>
        ))}
      </ol>
    </SectionCard>
  );
}