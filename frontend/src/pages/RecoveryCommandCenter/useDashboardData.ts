import { useCallback } from 'react';

import { getSummary, getTransactions } from '@/api';
import { useApiRequest } from '@/hooks';
import type { SummaryResponse, TransactionListResponse } from '@/types';

export interface DashboardData {
  summary: SummaryResponse;
  transactions: TransactionListResponse;
}

const RECENT_FAILED_LIMIT = 10;

function fetchDashboard(): Promise<DashboardData> {
  return Promise.all([
    getSummary(),
    getTransactions({ status: 'failed', limit: RECENT_FAILED_LIMIT }),
  ]).then(([summary, transactions]) => ({ summary, transactions }));
}

export function useDashboardData() {
  const { data, error, loading, refresh } = useApiRequest<DashboardData>(
    fetchDashboard,
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