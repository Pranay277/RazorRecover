import { useLocation } from 'react-router-dom';

import { API_BASE_URL } from '@/api';

import styles from './Header.module.css';

const TITLE_BY_PATH: Array<[RegExp, string]> = [
  [/^\/transactions\/\d+\/?$/, 'Transaction Details'],
  [/^\/transactions/, 'Transactions'],
  [/^\/audit/, 'Audit Logs'],
  [/^\//, 'Overview'],
];

function titleFor(pathname: string): string {
  for (const [pattern, title] of TITLE_BY_PATH) {
    if (pattern.test(pathname)) {
      return title;
    }
  }
  return 'RazorRecover';
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
  return (
    <header className={styles.header}>
      <h1 className={styles.title}>{titleFor(pathname)}</h1>
      <span className={styles.badge} title="Backend API base URL">
        API · {apiHost()}
      </span>
    </header>
  );
}