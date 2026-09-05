import styles from './RecoveryProbability.module.css';

export function RecoveryProbability() {
  return (
    <div className={styles.wrap}>
      <svg
        className={styles.icon}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        aria-hidden="true"
      >
        <path d="M4 20h16" />
        <path d="M6 20V8M10 20V13M14 20V5M18 20V10" />
      </svg>
      <p className={styles.title}>No aggregate probability data</p>
      <p className={styles.message}>
        Recovery probability is computed per transaction during evaluation and shown on the
        Transaction Details screen. There is no aggregate distribution endpoint yet, so this
        chart is intentionally empty.
      </p>
    </div>
  );
}