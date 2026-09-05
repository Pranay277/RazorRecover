import { useState } from 'react';

import { EmptyState, ErrorState, Loading } from '@/components';

import { EMPTY_FILTERS, PAGE_SIZE, type AppliedFilters } from './constants';
import { FilterBar } from './components/FilterBar';
import { Pagination } from './components/Pagination';
import { SummaryStrip } from './components/SummaryStrip';
import { TransactionsTable } from './components/TransactionsTable';
import { useTransactionsData } from './useTransactionsData';

import styles from './index.module.css';

export function TransactionsInvestigation() {
  const [draft, setDraft] = useState<AppliedFilters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<AppliedFilters>(EMPTY_FILTERS);
  const [page, setPage] = useState(0);

  const offset = page * PAGE_SIZE;
  const { summary, transactions, error, loading, reload } = useTransactionsData(
    applied,
    offset,
    PAGE_SIZE,
  );

  const patchDraft = (changes: Partial<AppliedFilters>) => {
    setDraft((previous) => ({ ...previous, ...changes }));
  };

  const applyFilters = () => {
    setApplied(draft);
    setPage(0);
  };

  const clearFilters = () => {
    setDraft(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
    setPage(0);
  };

  const previousPage = () => setPage((currentPage) => Math.max(0, currentPage - 1));
  const nextPage = () => setPage((currentPage) => currentPage + 1);

  if (error) {
    return (
      <ErrorState
        message="Could not load transactions from the recovery backend."
        details={error.message}
        onRetry={reload}
      />
    );
  }

  const items = transactions?.items ?? [];
  const total = transactions?.total ?? 0;
  const rangeFrom = total === 0 ? 0 : offset + 1;
  const rangeTo = total === 0 ? 0 : Math.min(offset + items.length, total);
  const hasPrevious = page > 0;
  const hasNext = total > offset + items.length;

  return (
    <div className={styles.page}>
      <SummaryStrip summary={summary} />

      <section className={styles.card}>
        <FilterBar
          draft={draft}
          onChange={patchDraft}
          onApply={applyFilters}
          onClear={clearFilters}
        />

        <div className={styles.tableArea}>
          {loading && !transactions ? (
            <Loading label="Loading transactions…" />
          ) : total === 0 ? (
            <EmptyState
              title="No transactions found"
              message="No transactions match the current filters. Clear the filters or expand the date range to see more."
            />
          ) : (
            <TransactionsTable items={items} />
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