import { NavLink, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';

import styles from './Sidebar.module.css';

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
  /** Custom active matcher. Deduped against the route's own matching rules. */
  match?: RegExp;
  icon: ReactNode;
}

function DashboardIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <rect x="9" y="1.5" width="5.5" height="5.5" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <rect x="1.5" y="9" width="5.5" height="5.5" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <rect x="9" y="9" width="5.5" height="5.5" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

function TransactionIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1.5" y="2.5" width="13" height="11" rx="2" stroke="currentColor" strokeWidth="1.4" />
      <path d="M1.5 5.5h13" stroke="currentColor" strokeWidth="1.4" />
      <path d="M4 12.5v-2M6.5 12.5v-2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function DetailsIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="2.5" y="1.5" width="11" height="13" rx="2" stroke="currentColor" strokeWidth="1.4" />
      <path d="M5 5h6M5 8h6M5 11h3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function AuditIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M2.5 3.5h11M2.5 7h11M2.5 10.5h7M2.5 14h11" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M4 10.5v3.5M6.5 10.5v3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Recovery Command Center Refined', end: true, icon: <DashboardIcon /> },
  {
    to: '/transactions',
    label: 'Transactions Investigation',
    match: /^\/transactions\/?$/,
    icon: <TransactionIcon />,
  },
  {
    to: '/transaction-details',
    label: 'Transaction Details',
    match: /^(\/transaction-details\/?|\/transactions\/\d+\/?)$/,
    icon: <DetailsIcon />,
  },
  { to: '/audit', label: 'Audit logs', icon: <AuditIcon /> },
];

function isNavActive(item: NavItem, pathname: string): boolean {
  if (item.match) {
    return item.match.test(pathname);
  }
  if (item.end) {
    return pathname === item.to;
  }
  return pathname.startsWith(item.to);
}

export function Sidebar() {
  const { pathname } = useLocation();
  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <span className={styles.brandName}>RazorRecover</span>
        <span className={styles.brandSub}>Merchant Ops</span>
      </div>
      <nav className={styles.nav} aria-label="Main">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={[
              styles.link,
              isNavActive(item, pathname) && styles.active,
            ]
              .filter(Boolean)
              .join(' ')}
          >
            <span className={styles.icon}>{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className={styles.footer}>Deterministic shield · v0.1</div>
    </aside>
  );
}