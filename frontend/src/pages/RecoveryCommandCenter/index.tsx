import { EmptyState, ErrorState, Loading } from '@/components';
import { formatCount, formatMoneyCompact, formatPercent } from '@/utils';

import { KpiCard } from './components/KpiCard';
import { ChartCard } from './components/ChartCard';
import { RecoveryOutcomesChart } from './components/RecoveryOutcomesChart';
import { RiskDistribution } from './components/RiskDistribution';
import { RecoveryProbability } from './components/RecoveryProbability';
import { InsightsPanel } from './components/InsightsPanel';
import { RecentFailedTable } from './components/RecentFailedTable';
import { recoveryRate } from './compute';
import { useDashboardData } from './useDashboardData';

import styles from './index.module.css';

export function RecoveryCommandCenter() {
  const { summary, transactions, error, loading, reload } = useDashboardData();

  if (loading) {
    return <Loading label="Loading recovery command center…" />;
  }

  if (error) {
    return (
      <ErrorState
        message="Could not load dashboard data from the recovery backend."
        details={error.message}
        onRetry={reload}
      />
    );
  }

  if (!summary) {
    return (
      <EmptyState
        title="No dashboard data"
        message="The command center could not be populated because the backend returned no summary."
      />
    );
  }

  const failedCount = summary.transactions_by_status.failed ?? 0;
  const recoveredCount = summary.transactions_by_status.recovered ?? 0;
  const rate = recoveryRate(failedCount, recoveredCount);

  return (
    <div className={styles.page}>
      <section className={styles.kpis} aria-label="Key metrics">
        <KpiCard
          label="Failed Payments"
          value={formatCount(failedCount)}
          sub="In investigation"
        />
        <KpiCard
          label="Recoverable Amount"
          value={formatMoneyCompact(summary.failed_amount)}
          sub="Failed transactions"
          mono
        />
        <KpiCard
          label="Recovered Revenue"
          value={formatMoneyCompact(summary.recovered_amount)}
          sub="Recovered transactions"
          mono
        />
        <KpiCard
          label="Recovery Rate"
          value={rate === null ? '—' : formatPercent(rate)}
          sub="Recovered over failed"
        />
      </section>

      <div className={styles.columns}>
        <div className={styles.workbench}>
          <section className={styles.section} aria-label="Recovery analytics">
            <h2 className={styles.sectionLabel}>Recovery Analytics</h2>
            <div className={styles.charts}>
              <ChartCard title="Recovery Outcomes">
                <RecoveryOutcomesChart counts={summary.recovery_decisions_by_outcome} />
              </ChartCard>
              <ChartCard title="Recovery Probability">
                <RecoveryProbability buckets={summary.recovery_decisions_by_probability_bucket} />
              </ChartCard>
              <ChartCard title="Risk Distribution">
                <RiskDistribution
                  buckets={summary.recovery_decisions_by_risk_bucket}
                  total={summary.recovery_decisions_total}
                />
              </ChartCard>
            </div>
          </section>

          <section className={styles.section} aria-label="Recent failed payments">
            <h2 className={styles.sectionLabel}>Recent Failed Payments</h2>
            <div className={styles.tableCard}>
              <RecentFailedTable items={transactions?.items ?? []} />
            </div>
          </section>
        </div>

        <InsightsPanel summary={summary} />
      </div>
    </div>
  );
}