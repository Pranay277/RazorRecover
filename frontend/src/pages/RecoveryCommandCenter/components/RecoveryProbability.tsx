import { formatCount, formatPercent } from '@/utils';

import styles from './RecoveryProbability.module.css';

type Tone = 'success' | 'warning' | 'danger' | 'neutral';

interface BucketDef {
  key: string;
  label: string;
  tone: Tone;
}

const BUCKETS: BucketDef[] = [
  { key: '0-20', label: '0–20%', tone: 'danger' },
  { key: '20-40', label: '20–40%', tone: 'warning' },
  { key: '40-60', label: '40–60%', tone: 'neutral' },
  { key: '60-80', label: '60–80%', tone: 'success' },
  { key: '80-100', label: '80–100%', tone: 'success' },
  { key: 'unknown', label: 'Unknown', tone: 'neutral' },
];

function toneClass(tone: Tone): string {
  return styles[`tone${tone.charAt(0).toUpperCase()}${tone.slice(1)}`];
}

export function RecoveryProbability({ buckets }: { buckets: Record<string, number> }) {
  const total = Object.values(buckets).reduce((sum, count) => sum + (count ?? 0), 0);

  if (total === 0) {
    return <p className={styles.empty}>No evaluated recovery probabilities yet.</p>;
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
      <p className={styles.foot}>{formatCount(total)} evaluated decisions</p>
    </div>
  );
}