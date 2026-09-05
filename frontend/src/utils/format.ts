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

/**
 * Compact money for KPI cards (e.g. "$86.4K", "$312.8K"). Used only for
 * large dashboard aggregates where the exact decimal digits are secondary.
 */
export function formatMoneyCompact(
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
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value);
  } catch {
    return `${value.toFixed(0)} ${currency}`;
  }
}

/** Plain integer count with thousands separators (e.g. "1,284"). */
export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  return value.toLocaleString('en-US');
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

/** Compact "YYYY-MM-DD HH:mm" rendering for table timestamp columns. */
export function formatDateTimeCompact(iso: string | null | undefined): string {
  if (!iso) {
    return '—';
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }
  const pad = (value: number) => String(value).padStart(2, '0');
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  const fields = [
    local.getUTCFullYear(),
    pad(local.getUTCMonth() + 1),
    pad(local.getUTCDate()),
  ].join('-');
  return `${fields} ${pad(local.getUTCHours())}:${pad(local.getUTCMinutes())}`;
}