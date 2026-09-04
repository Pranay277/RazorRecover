import { Button } from './Button';

import styles from './ErrorState.module.css';

interface ErrorStateProps {
  title?: string;
  message: string;
  details?: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = 'Something went wrong',
  message,
  details,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className={styles.wrap} role="alert">
      <svg
        className={styles.icon}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="8.5" />
        <path d="M12 8v4.5M12 15.8h.01" />
      </svg>
      <h3 className={styles.title}>{title}</h3>
      <p className={styles.message}>{message}</p>
      {details && <p className={styles.details}>{details}</p>}
      {onRetry && (
        <div className={styles.actions}>
          <Button variant="secondary" onClick={onRetry}>
            Try again
          </Button>
        </div>
      )}
    </div>
  );
}