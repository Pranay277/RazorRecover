import type { ReactNode } from 'react';

import styles from './Card.module.css';

interface CardProps {
  title?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}

export function Card({ title, actions, children, className }: CardProps) {
  const classes = [styles.card, className].filter(Boolean).join(' ');
  return (
    <section className={classes}>
      {(title || actions) && (
        <header className={styles.header}>
          {title && <h2 className={styles.title}>{title}</h2>}
          {actions && <div className={styles.actions}>{actions}</div>}
        </header>
      )}
      <div className={styles.body}>{children}</div>
    </section>
  );
}