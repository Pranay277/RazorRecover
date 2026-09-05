import { useCallback } from 'react';

import { getSummary, getTransactions } from '@/api';
import type { TransactionListParams } from '@/api';
import { useApiRequest } from '@/hooks';
import type { SummaryResponse, TransactionListResponse } from '@/types';

import type { AppliedFilters } from './constants';

export interface TransactionsData {
  summary: SummaryResponse;
  transactions: TransactionListResponse;
}

function buildParams(applied: AppliedFilters, offset: number, limit: number): TransactionListParams {
  const params: TransactionListParams = { limit, offset };
  if (applied.status) {
    params.status = applied.status;
  }
  if (applied.payment_method) {
    params.payment_method = applied.payment_method;
  }
  if (applied.gateway) {
    params.gateway = applied.gateway;
  }
  if (applied.search) {
    params.search = applied.search;
  }
  if (applied.attempted_from) {
    params.attempted_from = applied.attempted_from;
  }
  if (applied.attempted_to) {
    params.attempted_to = applied.attempted_to;
  }
  return params;
}

function fetchTransactions(applied: AppliedFilters, offset: number, limit: number): Promise<TransactionsData> {
  return Promise.all([
    getSummary(),
    getTransactions(buildParams(applied, offset, limit)),
  ]).then(([summary, transactions]) => ({ summary, transactions }));
}

export function useTransactionsData(applied: AppliedFilters, offset: number, limit: number) {
  const { data, error, loading, refresh } = useApiRequest<TransactionsData>(
    useCallback(() => fetchTransactions(applied, offset, limit), [applied, offset, limit]),
    [applied, offset, limit],
  );

  const reload = useCallback(() => refresh(), [refresh]);

  return {
    summary: data?.summary ?? null,
    transactions: data?.transactions ?? null,
    error,
    loading,
    reload,
  };
}