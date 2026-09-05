import { useLocation } from 'react-router-dom';

import { API_BASE_URL } from '@/api';

import styles from './Header.module.css';

interface HeaderMeta {
  title: string;
  subtitle?: string;
}

const META_BY_PATH: Array<[RegExp, HeaderMeta]> = [
  [
    /^\/$/,
    {
      title: 'Recovery Command Center',
      subtitle: 'Monitor failed payments and recovery decisions',
    },
  ],
  [
    /^\/transactions\/\d+\/?$/,
    {
      title: 'Transaction Details',
      subtitle: 'Investigate payment failure, recovery analysis, and decision history',
    },
  ],
  [
    /^\/transactions/,
    {
      title: 'Transactions',
      subtitle: 'Select a transaction to view its details',
    },
  ],
  [/^\/audit/, { title: 'Audit logs', subtitle: 'Inspect recovery workflow events and decision outcomes' }],
  [/^\//, { title: 'RazorRecover' }],
];

function metaFor(pathname: string): HeaderMeta {
  for (const [pattern, meta] of META_BY_PATH) {
    if (pattern.test(pathname)) {
      return meta;
    }
  }
  return { title: 'RazorRecover' };
}

function apiHost(): string {
  try {
    return new URL(API_BASE_URL).host;
  } catch {
    return API_BASE_URL;
  }
}

export function Header() {
  const { pathname } = useLocation();
  const { title, subtitle } = metaFor(pathname);
  return (
    <header className={styles.header}>
      <div className={styles.heading}>
        <h1 className={styles.title}>{title}</h1>
        {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
      </div>
      <span className={styles.badge} title="Backend API base URL">
        API · {apiHost()}
      </span>
    </header>
  );
}