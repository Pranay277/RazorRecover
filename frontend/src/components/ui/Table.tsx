import type { ReactNode } from 'react';

import styles from './Table.module.css';

type CellAlign = 'left' | 'center' | 'right';

interface TableCellProps {
  align?: CellAlign;
  mono?: boolean;
  children?: ReactNode;
  className?: string;
  colSpan?: number;
}

export function Table({ children, className }: { children?: ReactNode; className?: string }) {
  const classes = [styles.table, className].filter(Boolean).join(' ');
  return (
    <div className={styles.scroll}>
      <table className={classes}>{children}</table>
    </div>
  );
}

export function THead({ children }: { children?: ReactNode }) {
  return <thead className={styles.head}>{children}</thead>;
}

export function TBody({ children }: { children?: ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function TRow({ children, onClick }: { children?: ReactNode; onClick?: () => void }) {
  const classes = [styles.row, onClick && styles.clickable].filter(Boolean).join(' ');
  return (
    <tr className={classes} onClick={onClick}>
      {children}
    </tr>
  );
}

export function THeadCell({
  align = 'left',
  children,
  className,
}: Omit<TableCellProps, 'mono' | 'colSpan'>) {
  const classes = [styles.th, align !== 'left' && styles[`align${align}`], className]
    .filter(Boolean)
    .join(' ');
  return <th className={classes}>{children}</th>;
}

export function TCell({
  align = 'left',
  mono = false,
  children,
  className,
  colSpan,
}: TableCellProps) {
  const classes = [
    styles.td,
    align !== 'left' && styles[`align${align}`],
    mono && 'mono',
    className,
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <td className={classes} colSpan={colSpan}>
      {children}
    </td>
  );
}