/**
 * Formatting helpers shared across screens. Amounts arrive from the backend as
 * Decimal-serialized strings; timestamps are ISO-8601 strings.
 */

const DATE_ONLY = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
});

const DATE_TIME = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
});

function toNumber(amount: string | number | null | undefined): number | null {
  if (amount === null || amount === undefined || amount === '') {
    return null;
  }
  const value = typeof amount === 'string' ? Number(amount) : amount;
  return Number.isNaN(value) ? null : value;
}

export function formatMoney(
  amount: string | number | null | undefined,
  currency = 'USD',
): string {
  const value = toNumber(amount);
  if (value === null) {
    return '—';
  }
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
    }).format(value);
  } catch {
    return `${value.toFixed(2)} ${currency}`;
  }
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  return `${value.toLocaleString('en-US', { maximumFractionDigits: 1 })}%`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) {
    return '—';
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }
  return DATE_ONLY.format(date);
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) {
    return '—';
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }
  return DATE_TIME.format(date);
}