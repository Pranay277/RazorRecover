import type { ReactNode } from 'react';

import styles from './SectionHeading.module.css';

interface SectionHeadingProps {
  icon?: ReactNode;
  label: string;
  sub?: string;
}

export function SectionHeading({ icon, label, sub }: SectionHeadingProps) {
  return (
    <div className={styles.heading}>
      {icon && <span className={styles.icon}>{icon}</span>}
      <div className={styles.text}>
        <span className={styles.label}>{label}</span>
        {sub && <span className={styles.sub}>{sub}</span>}
      </div>
    </div>
  );
}