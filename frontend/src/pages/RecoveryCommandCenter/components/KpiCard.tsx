import styles from './KpiCard.module.css';

interface KpiCardProps {
  label: string;
  value: string;
  sub?: string;
  mono?: boolean;
}

export function KpiCard({ label, value, sub, mono = false }: KpiCardProps) {
  const valueClasses = [styles.value, mono && styles.mono]
    .filter(Boolean)
    .join(' ');
  return (
    <section className={styles.kpi}>
      <div className={styles.label}>{label}</div>
      <div className={valueClasses}>{value}</div>
      {sub && <div className={styles.sub}>{sub}</div>}
    </section>
  );
}