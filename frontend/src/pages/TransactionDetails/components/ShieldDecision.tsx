import { shieldBadge } from '@/utils';
import type { RecoveryDecisionRead, ShieldRuleResult, TransactionDetail } from '@/types';

import { SectionCard } from './SectionCard';
import { SectionHeading } from './SectionHeading';

import styles from './ShieldDecision.module.css';

interface ShieldDecisionProps {
  transaction: TransactionDetail;
  latestDecision: RecoveryDecisionRead | null;
}

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M12 3 5 6v5c0 4.4 3 7.6 7 9 4-1.4 7-4.6 7-9V6l-7-3Z" strokeLinejoin="round" />
      <polyline points="9 11.8 11 13.8 15.5 9.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ShieldDecision({ transaction, latestDecision }: ShieldDecisionProps) {
  const rules = transaction.shield_rule_results ?? [];
  const outcome = latestDecision?.outcome ?? null;
  const badge = shieldBadge(outcome);
  const verdictTone = toneClass(badge.tone);
  const noDecision = !latestDecision;

  return (
    <SectionCard
      title={
        <SectionHeading
          icon={<ShieldIcon />}
          label="Shield Decision"
          sub="Deterministic policy evaluation"
        />
      }
      footer={<span className={styles.footer}>{footerFor(outcome, noDecision)}</span>}
    >
      <div className={styles.verdictHero}>
        <div className={styles.verdictText}>
          <span className={styles.verdictLabel}>Policy verdict</span>
          <span className={styles.verdictLine}>
            {noDecision
              ? 'No shield evaluation recorded'
              : rules.length > 0
                ? `Validated against ${rules.length} merchant policy rule${rules.length === 1 ? '' : 's'}`
                : 'No rule results persisted for this evaluation'}
          </span>
        </div>
        <span className={`${styles.verdictPill} ${verdictTone}`}>{badge.label}</span>
      </div>

      {latestDecision && (
        <p className={styles.policyMeta}>
          Policy v<span className={styles.mono}>{latestDecision.policy_version ?? '—'}</span>
          {' · '}Decision #<span className={styles.mono}>{latestDecision.id}</span>
          {' · '}
          <span className={styles.mono}>{new Date(latestDecision.decided_at).toLocaleString()}</span>
        </p>
      )}

      <div className={styles.rulesHead}>
        <span>Rule evaluation</span>
        <span className={styles.rulesCount}>{rules.length} checked</span>
      </div>

      {rules.length > 0 ? (
        <ul className={styles.ruleList}>
          {rules.map((rule: ShieldRuleResult) => (
            <li key={rule.rule} className={styles.rule}>
              <span className={`${styles.ruleMark} ${rule.passed ? styles.pass : styles.fail}`}>
                {rule.passed ? 'PASS' : 'FAIL'}
              </span>
              <span className={styles.ruleName}>{rule.rule}</span>
              {rule.disposition && (
                <span
                  className={`${styles.ruleDisposition} ${rule.passed ? styles.pass : styles.fail}`}
                >
                  {rule.disposition}
                </span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.noRules}>
          {noDecision
            ? 'No shield rule results were persisted for this transaction.'
            : 'This evaluation produced no per-rule results.'}
        </p>
      )}
    </SectionCard>
  );
}

function toneClass(tone: string): string {
  switch (tone) {
    case 'success':
      return styles.toneSuccess;
    case 'warning':
      return styles.toneWarning;
    case 'danger':
      return styles.toneDanger;
    default:
      return styles.toneNeutral;
  }
}

function footerFor(outcome: string | null, noDecision: boolean): string {
  if (noDecision || !outcome) {
    return 'No shield evaluation was persisted for this transaction.';
  }
  switch (outcome) {
    case 'authorized':
      return 'Shield validated this recommendation against merchant policy rules. This is a read-only view — no action was auto-executed.';
    case 'review':
      return 'Shield flagged this recommendation for manual review before execution. Nothing was scheduled from this view.';
    case 'blocked':
    case 'denied':
      return 'Shield rejected this recommendation under merchant policy, so it was not scheduled for execution.';
    default:
      return 'Shield evaluated this recommendation deterministically against merchant policy.';
  }
}