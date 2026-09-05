import { formatCount } from '@/utils';
import type { SummaryResponse } from '@/types';

import styles from './SummaryStrip.module.css';

interface SummaryStripProps {
  summary: SummaryResponse | null;
}

export function SummaryStrip({ summary }: SummaryStripProps) {
  const stats = [
    { label: 'Total', value: summary?.total_transactions },
    { label: 'Failed', value: summary?.transactions_by_status.failed },
    { label: 'Recovered', value: summary?.transactions_by_status.recovered },
    { label: 'Pending Review', value: summary?.recovery_decisions_by_outcome.review },
  ];

  return (
    <div className={styles.strip} aria-label="Transaction summary">
      {stats.map((stat) => (
        <div key={stat.label} className={styles.cell}>
          <span className={styles.label}>{stat.label}</span>
          <span className={styles.value}>{formatCount(stat.value)}</span>
        </div>
      ))}
    </div>
  );
}