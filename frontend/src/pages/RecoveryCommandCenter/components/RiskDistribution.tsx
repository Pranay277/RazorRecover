import { formatCount, formatPercent } from '@/utils';

import styles from './RiskDistribution.module.css';

type Tone = 'success' | 'warning' | 'danger' | 'neutral';

interface BucketDef {
  key: string;
  label: string;
  tone: Tone;
}

const BUCKETS: BucketDef[] = [
  { key: 'low', label: 'Low', tone: 'success' },
  { key: 'medium', label: 'Medium', tone: 'warning' },
  { key: 'high', label: 'High', tone: 'danger' },
  { key: 'unknown', label: 'Unknown', tone: 'neutral' },
];

function toneClass(tone: Tone): string {
  return styles[`tone${tone.charAt(0).toUpperCase()}${tone.slice(1)}`];
}

export function RiskDistribution({
  buckets,
  total,
}: {
  buckets: Record<string, number>;
  total: number;
}) {
  if (total === 0) {
    return <p className={styles.empty}>No risk scores recorded yet.</p>;
  }

  return (
    <div>
      <ul className={styles.legend}>
        {BUCKETS.map((bucket) => {
          const count = buckets[bucket.key] ?? 0;
          return (
            <li key={bucket.key} className={styles.row}>
              <span className={`${styles.dot} ${toneClass(bucket.tone)}`} aria-hidden="true" />
              <span>{bucket.label}</span>
              <span className={styles.rowValue}>
                {formatCount(count)}
                <span>{formatPercent(count > 0 ? (count / total) * 100 : 0)}</span>
              </span>
            </li>
          );
        })}
      </ul>
      <p className={styles.foot}>{formatCount(total)} decisions assessed</p>
    </div>
  );
}