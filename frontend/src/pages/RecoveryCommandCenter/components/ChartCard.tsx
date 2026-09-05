import type { ReactNode } from 'react';

import { Card } from '@/components';

import styles from './ChartCard.module.css';

interface ChartCardProps {
  title: string;
  children: ReactNode;
  className?: string;
}

export function ChartCard({ title, children, className }: ChartCardProps) {
  const classes = [styles.card, className].filter(Boolean).join(' ');
  return (
    <Card className={classes} title={title}>
      <div className={styles.body}>{children}</div>
    </Card>
  );
}