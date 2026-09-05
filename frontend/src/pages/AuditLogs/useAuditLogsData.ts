import { useCallback } from 'react';

import { getAuditLogs } from '@/api';
import type { AuditListParams } from '@/api';
import { useApiRequest } from '@/hooks';
import type { AuditListResponse } from '@/types';

export function useAuditLogsData(
  transactionId: number | null,
  offset: number,
  limit: number,
) {
  const fetcher = useCallback(() => {
    const params: AuditListParams = { limit, offset };
    if (transactionId !== null) {
      params.transaction_id = transactionId;
    }
    return getAuditLogs(params);
  }, [transactionId, offset, limit]);

  const { data, error, loading, refresh } = useApiRequest<AuditListResponse>(
    fetcher,
    [transactionId, offset, limit],
  );

  const reload = useCallback(() => refresh(), [refresh]);

  return {
    data: data ?? null,
    error,
    loading,
    reload,
  };
}