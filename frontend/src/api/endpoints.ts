/**
 * Typed endpoint definitions. Each function maps 1:1 to a backend route.
 */

import { request, toQueryString } from './client';

import type {
  AuditListResponse,
  EvaluateRequest,
  EvaluateResponse,
  SummaryResponse,
  TransactionDetail,
  TransactionListResponse,
} from '../types';

export interface TransactionListParams {
  status?: string;
  merchant_id?: number;
  customer_id?: number;
  payment_method?: string;
  gateway?: string;
  failure_code?: string;
  search?: string;
  created_from?: string;
  created_to?: string;
  limit?: number;
  offset?: number;
}

export interface AuditListParams {
  transaction_id?: number;
  limit?: number;
  offset?: number;
}

export function getTransactions(params: TransactionListParams = {}): Promise<TransactionListResponse> {
  return request<TransactionListResponse>(`/api/v1/transactions${toQueryString(params)}`);
}

export function getTransaction(transactionId: number): Promise<TransactionDetail> {
  return request<TransactionDetail>(`/api/v1/transactions/${transactionId}`);
}

export function getSummary(): Promise<SummaryResponse> {
  return request<SummaryResponse>('/api/v1/summary');
}

export function getAuditLogs(params: AuditListParams = {}): Promise<AuditListResponse> {
  return request<AuditListResponse>(`/api/v1/audit${toQueryString(params)}`);
}

export function evaluateRecovery(payload: EvaluateRequest): Promise<EvaluateResponse> {
  return request<EvaluateResponse>('/api/v1/recovery/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}