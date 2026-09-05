import { Button } from '@/components';
import { formatCount } from '@/utils';

import styles from './Pagination.module.css';

interface PaginationProps {
  total: number;
  from: number;
  to: number;
  hasPrevious: boolean;
  hasNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
}

export function Pagination({
  total,
  from,
  to,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
}: PaginationProps) {
  return (
    <div className={styles.bar}>
      <span className={styles.range}>
        Showing {from}–{to} of {formatCount(total)} events
      </span>
      <div className={styles.actions}>
        <Button variant="secondary" size="sm" onClick={onPrevious} disabled={!hasPrevious}>
          Previous
        </Button>
        <Button variant="secondary" size="sm" onClick={onNext} disabled={!hasNext}>
          Next
        </Button>
      </div>
    </div>
  );
}