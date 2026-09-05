/**
 * Filters for the Audit Logs screen.
 *
 * The backend endpoint only supports `transaction_id` filtering, so the UI
 * exposes exactly that plus pagination (`limit`/`offset`). Any flow that wants
 * actor/action/outcome filtering on the server side is intentionally absent -
 * the API does not provide it.
 */

export interface AppliedFilters {
  /** Draft transaction id as typed by the operator ('' = no filter). */
  transactionId: string;
}

export const EMPTY_FILTERS: AppliedFilters = {
  transactionId: '',
};

/** Draft -> request value. Returns null when no filter should be sent. */
export function parseTransactionId(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  if (!/^\d+$/.test(trimmed)) {
    return null;
  }
  const parsed = Number(trimmed);
  return parsed >= 1 ? parsed : null;
}

/** A draft is applicable when empty or a positive integer. */
export function isValidTransactionId(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) {
    return true;
  }
  return /^\d+$/.test(trimmed) && Number(trimmed) >= 1;
}

export const PAGE_SIZE = 50;