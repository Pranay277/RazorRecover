import { NavLink } from 'react-router-dom';

import styles from './Sidebar.module.css';

const NAV_ITEMS = [
  { to: '/', label: 'Overview', end: true },
  { to: '/transactions', label: 'Transactions', end: false },
  { to: '/audit', label: 'Audit Logs', end: false },
];

export function Sidebar() {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <span className={styles.brandName}>RazorRecover</span>
        <span className={styles.brandSub}>Payment recovery</span>
      </div>
      <nav className={styles.nav} aria-label="Main">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              [styles.link, isActive && styles.active].filter(Boolean).join(' ')
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className={styles.footer}>Deterministic shield · v0.1</div>
    </aside>
  );
}