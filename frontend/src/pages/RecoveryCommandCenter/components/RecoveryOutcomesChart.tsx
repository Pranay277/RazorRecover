import { formatCount, formatPercent } from '@/utils';

import styles from './RecoveryOutcomesChart.module.css';

type Tone = 'success' | 'warning' | 'danger' | 'neutral';

interface SegmentDef {
  key: string;
  label: string;
  tone: Tone;
}

interface Segment extends SegmentDef {
  count: number;
  share: number;
}

const KNOWN_SEGMENTS: SegmentDef[] = [
  { key: 'authorized', label: 'Authorized', tone: 'success' },
  { key: 'review', label: 'Review', tone: 'warning' },
  { key: 'blocked', label: 'Blocked', tone: 'danger' },
  { key: 'denied', label: 'Denied', tone: 'danger' },
];

function toneClass(tone: Tone): string {
  return styles[`tone${tone.charAt(0).toUpperCase()}${tone.slice(1)}`];
}

function buildSegments(counts: Record<string, number>): Segment[] {
  const knownKeys = new Set(KNOWN_SEGMENTS.map((segment) => segment.key));
  const total = Object.values(counts).reduce((sum, count) => sum + count, 0);

  let otherCount = 0;
  for (const [key, count] of Object.entries(counts)) {
    if (!knownKeys.has(key)) {
      otherCount += count;
    }
  }

  const segments: Segment[] = KNOWN_SEGMENTS.map((definition) => ({
    ...definition,
    count: counts[definition.key] ?? 0,
    share: 0,
  }));
  if (otherCount > 0) {
    segments.push({ key: 'other', label: 'Other', tone: 'neutral', count: otherCount, share: 0 });
  }

  return segments.filter((segment) => segment.count > 0).map((segment) => ({
    ...segment,
    share: total > 0 ? (segment.count / total) * 100 : 0,
  }));
}

export function RecoveryOutcomesChart({ counts }: { counts: Record<string, number> }) {
  const segments = buildSegments(counts);
  const total = segments.reduce((sum, segment) => sum + segment.count, 0);

  if (total === 0) {
    return <p className={styles.empty}>No recovery decisions recorded yet.</p>;
  }

  return (
    <div>
      <div
        className={styles.bar}
        role="img"
        aria-label={`Recovery outcomes: ${segments
          .map((segment) => `${segment.label} ${segment.count}`)
          .join(', ')}`}
      >
        {segments.map((segment) => (
          <div
            key={segment.key}
            className={`${styles.segment} ${toneClass(segment.tone)}`}
            style={{ width: `${segment.share}%` }}
            title={`${segment.label}: ${segment.count}`}
          />
        ))}
      </div>
      <ul className={styles.legend}>
        {segments.map((segment) => (
          <li key={segment.key} className={styles.row}>
            <span className={`${styles.dot} ${toneClass(segment.tone)}`} aria-hidden="true" />
            <span>{segment.label}</span>
            <span className={styles.rowValue}>
              {formatCount(segment.count)}
              <span>{formatPercent(segment.share)}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}