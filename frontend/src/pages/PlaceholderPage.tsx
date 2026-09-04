import { EmptyState } from '@/components';

import styles from './PlaceholderPage.module.css';

interface PlaceholderPageProps {
  title: string;
  description?: string;
}

/**
 * Temporary stand-in for every screen while STEP 1 foundation is in place.
 * The four real screens (Overview, Transactions, Transaction Details, Audit
 * Logs) are implemented in later steps.
 */
export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <div className={styles.wrap}>
      <EmptyState title={`${title} coming soon`} message={description} />
    </div>
  );
}