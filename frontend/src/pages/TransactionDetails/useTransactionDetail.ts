import { useCallback } from 'react';

import { getTransaction } from '@/api';
import { useApiRequest } from '@/hooks';
import type { TransactionDetail } from '@/types';

export function useTransactionDetail(transactionId: number | null) {
  const { data, error, loading, refresh } = useApiRequest<TransactionDetail>(
    useCallback(() => getTransaction(transactionId as number), [transactionId]),
    [transactionId],
    transactionId !== null,
  );

  const reload = useCallback(() => refresh(), [refresh]);

  return {
    detail: data ?? null,
    error,
    loading,
    reload,
  };
}