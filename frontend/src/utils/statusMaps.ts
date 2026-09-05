/**
 * Shared status-to-display mappings for list/detail screens. Every mapping
 * interprets real backend values only - no values are invented here.
 */

import type { BadgeTone } from '@/components';

// -- risk --------------------------------------------------------------------

export type RiskLevel = 'low' | 'medium' | 'high' | 'unknown';

export function riskLevel(risk: string | number | null | undefined): RiskLevel {
  if (risk === null || risk === undefined || risk === '') {
    return 'unknown';
  }
  const value = typeof risk === 'string' ? Number(risk) : risk;
  if (Number.isNaN(value)) {
    return 'unknown';
  }
  if (value < 0.33) {
    return 'low';
  }
  if (value < 0.66) {
    return 'medium';
  }
  return 'high';
}

const RISK_BADGE: Record<RiskLevel, { label: string; tone: BadgeTone }> = {
  low: { label: 'Low', tone: 'success' },
  medium: { label: 'Medium', tone: 'warning' },
  high: { label: 'High', tone: 'danger' },
  unknown: { label: 'Unknown', tone: 'neutral' },
};

export function riskBadge(risk: string | number | null | undefined) {
  return RISK_BADGE[riskLevel(risk)];
}

// -- shield outcome ----------------------------------------------------------

const OUTCOME_BADGE: Record<string, { label: string; tone: BadgeTone }> = {
  authorized: { label: 'Allowed', tone: 'success' },
  review: { label: 'Review', tone: 'warning' },
  blocked: { label: 'Blocked', tone: 'danger' },
  denied: { label: 'Blocked', tone: 'danger' },
};

export function shieldBadge(outcome: string | null | undefined) {
  if (outcome && OUTCOME_BADGE[outcome]) {
    return OUTCOME_BADGE[outcome];
  }
  return { label: 'Pending', tone: 'neutral' as BadgeTone };
}

// -- recovery attempts -------------------------------------------------------

const ATTEMPT_BADGE: Record<string, { label: string; tone: BadgeTone }> = {
  success: { label: 'Recovered', tone: 'success' },
  failed: { label: 'Failed', tone: 'danger' },
  running: { label: 'Running', tone: 'info' },
  pending: { label: 'Pending', tone: 'neutral' },
};

export function attemptBadge(status: string | null | undefined) {
  if (status && ATTEMPT_BADGE[status]) {
    return ATTEMPT_BADGE[status];
  }
  return { label: 'Not evaluated', tone: 'neutral' as BadgeTone };
}

// -- transaction status ------------------------------------------------------

const STATUS_BADGE: Record<string, { label: string; tone: BadgeTone }> = {
  failed: { label: 'Failed', tone: 'danger' },
  recovered: { label: 'Recovered', tone: 'success' },
  pending: { label: 'Pending', tone: 'warning' },
  abandoned: { label: 'Abandoned', tone: 'neutral' },
};

export function transactionStatusBadge(status: string | null | undefined) {
  if (status && STATUS_BADGE[status]) {
    return STATUS_BADGE[status];
  }
  return { label: status ?? '—', tone: 'neutral' as BadgeTone };
}

// -- AI action labels --------------------------------------------------------

const ACTION_LABELS: Record<string, string> = {
  RETRY_NOW: 'Auto-retry',
  DELAYED_RETRY: 'Delayed retry',
  ALTERNATIVE_PAYMENT: 'Alternate payment',
  CUSTOMER_NOTIFICATION: 'Notify customer',
  MANUAL_REVIEW: 'Manual review',
  STOP: 'Stop',
  retry: 'Auto-retry',
  switch_payment_method: 'Switch method',
  dunning_email: 'Dunning email',
  request_new_card: 'Request new card',
  hold_drop: 'Hold / drop',
};

export function humanizeAction(action: string | null | undefined): string {
  if (!action) {
    return '—';
  }
  return ACTION_LABELS[action] ?? action.replace(/_/g, ' ');
}