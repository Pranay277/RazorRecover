import type { ReactNode } from 'react';

import styles from './SectionCard.module.css';

interface SectionCardProps {
  title?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

/**
 * Card chrome for the transaction-details sections: bordered white surface
 * with an optional header (icon + title + aside) and an optional footer row.
 * Page-scoped wrapper; the generic shared Card stays the default elsewhere.
 */
export function SectionCard({ title, aside, children, footer, className }: SectionCardProps) {
  const classes = [styles.card, className].filter(Boolean).join(' ');
  return (
    <section className={classes}>
      {(title || aside) && (
        <header className={styles.head}>
          <div className={styles.title}>{title}</div>
          {aside && <div className={styles.aside}>{aside}</div>}
        </header>
      )}
      <div className={styles.body}>{children}</div>
      {footer && <div className={styles.footer}>{footer}</div>}
    </section>
  );
}