import { useState } from 'react';

import { EmptyState, ErrorState, Loading } from '@/components';

import {
  EMPTY_FILTERS,
  PAGE_SIZE,
  parseTransactionId,
  type AppliedFilters,
} from './constants';
import { AuditLogsTable } from './components/AuditLogsTable';
import { AuditSummaryStrip } from './components/AuditSummaryStrip';
import { FilterBar } from './components/FilterBar';
import { Pagination } from './components/Pagination';
import { useAuditLogsData } from './useAuditLogsData';

import styles from './index.module.css';

export function AuditLogs() {
  const [draft, setDraft] = useState<AppliedFilters>(EMPTY_FILTERS);
  const [transactionId, setTransactionId] = useState<number | null>(null);
  const [page, setPage] = useState(0);

  const offset = page * PAGE_SIZE;
  const { data, error, loading, reload } = useAuditLogsData(transactionId, offset, PAGE_SIZE);

  const patchDraft = (changes: Partial<AppliedFilters>) => {
    setDraft((previous) => ({ ...previous, ...changes }));
  };

  const applyFilters = () => {
    setTransactionId(parseTransactionId(draft.transactionId));
    setPage(0);
  };

  const clearFilters = () => {
    setDraft(EMPTY_FILTERS);
    setTransactionId(null);
    setPage(0);
  };

  const previousPage = () => setPage((currentPage) => Math.max(0, currentPage - 1));
  const nextPage = () => setPage((currentPage) => currentPage + 1);

  if (error) {
    return (
      <ErrorState
        message="Could not load audit events from the recovery backend."
        details={error.message}
        onRetry={reload}
      />
    );
  }

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const rangeFrom = total === 0 ? 0 : offset + 1;
  const rangeTo = total === 0 ? 0 : Math.min(offset + items.length, total);
  const hasPrevious = page > 0;
  const hasNext = total > offset + items.length;

  return (
    <div className={styles.page}>
      <AuditSummaryStrip data={data} />

      <section className={styles.card}>
        <FilterBar
          draft={draft}
          onChange={patchDraft}
          onApply={applyFilters}
          onClear={clearFilters}
        />

        <div className={styles.tableArea}>
          {loading && !data ? (
            <Loading label="Loading audit events…" />
          ) : total === 0 ? (
            transactionId !== null ? (
              <EmptyState
                title="No audit events for this transaction"
                message={`No persisted audit events reference transaction #${transactionId}. Clear the filter to see all events.`}
              />
            ) : (
              <EmptyState
                title="No audit events recorded"
                message="Audit events are appended when the recovery workflow evaluates a transaction. No events have been persisted yet."
              />
            )
          ) : (
            <AuditLogsTable items={items} />
          )}
        </div>

        {total > 0 && (
          <Pagination
            total={total}
            from={rangeFrom}
            to={rangeTo}
            hasPrevious={hasPrevious}
            hasNext={hasNext}
            onPrevious={previousPage}
            onNext={nextPage}
          />
        )}
      </section>
    </div>
  );
}