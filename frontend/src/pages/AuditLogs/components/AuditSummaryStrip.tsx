import { formatCount, formatDateTimeCompact } from '@/utils';
import type { AuditListResponse } from '@/types';

import styles from './AuditSummaryStrip.module.css';

interface AuditSummaryStripProps {
  data: AuditListResponse | null;
}

/**
 * Aggregate info derived strictly from the loaded / returned page. "Loaded"
 * is the number of events visible on this page; "Total" is the server-side
 * count returned by the endpoint (database-wide, respects the transaction
 * filter). No invented values.
 */
export function AuditSummaryStrip({ data }: AuditSummaryStripProps) {
  const items = data?.items ?? [];
  const latest = items.length > 0 ? items[0] : null;
  const actorCount = new Set(items.map((event) => event.actor).filter(Boolean)).size;

  const stats = [
    { label: 'Loaded Events', value: data ? formatCount(items.length) : '—' },
    { label: 'Total Events', value: data ? formatCount(data.total) : '—' },
    {
      label: 'Latest Event',
      value: latest ? formatDateTimeCompact(latest.occurred_at) : '—',
      mono: true,
    },
    { label: 'Actors (Loaded)', value: data ? formatCount(actorCount) : '—' },
  ];

  return (
    <div className={styles.strip} aria-label="Audit log summary">
      {stats.map((stat) => (
        <div key={stat.label} className={styles.cell}>
          <span className={styles.label}>{stat.label}</span>
          <span className={`${styles.value} ${stat.mono ? styles.mono : ''}`}>
            {stat.value}
          </span>
        </div>
      ))}
    </div>
  );
}