import styles from './Loading.module.css';

interface LoadingProps {
  label?: string;
}

export function Loading({ label = 'Loading…' }: LoadingProps) {
  return (
    <div className={styles.wrap} role="status" aria-live="polite">
      <span className={styles.spinner} aria-hidden="true" />
      <span className={styles.label}>{label}</span>
    </div>
  );
}