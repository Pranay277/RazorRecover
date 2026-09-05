import { Button } from '@/components';

import {
  GATEWAY_OPTIONS,
  METHOD_OPTIONS,
  STATUS_OPTIONS,
  type AppliedFilters,
} from '../constants';

import styles from './FilterBar.module.css';

interface FilterBarProps {
  draft: AppliedFilters;
  onChange: (changes: Partial<AppliedFilters>) => void;
  onApply: () => void;
  onClear: () => void;
}

export function FilterBar({ draft, onChange, onApply, onClear }: FilterBarProps) {
  const hasDraft =
    Boolean(draft.search) ||
    Boolean(draft.status) ||
    Boolean(draft.payment_method) ||
    Boolean(draft.gateway) ||
    Boolean(draft.attempted_from) ||
    Boolean(draft.attempted_to);

  return (
    <form
      className={styles.bar}
      onSubmit={(event) => {
        event.preventDefault();
        onApply();
      }}
    >
      <div className={styles.searchBox}>
        <label className={styles.visuallyHidden} htmlFor="tx-search">
          Search transactions
        </label>
        <svg
          className={styles.searchIcon}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="11" cy="11" r="7" />
          <path d="m21 21-4.3-4.3" />
        </svg>
        <input
          id="tx-search"
          className={styles.searchInput}
          type="search"
          placeholder="TXN ID / Customer"
          value={draft.search}
          onChange={(event) => onChange({ search: event.target.value })}
        />
      </div>

      <div className={styles.field}>
        <label className={styles.fieldLabel} htmlFor="tx-status">
          Status
        </label>
        <select
          id="tx-status"
          className={styles.select}
          value={draft.status}
          onChange={(event) => onChange({ status: event.target.value })}
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <label className={styles.fieldLabel} htmlFor="tx-method">
          Method
        </label>
        <select
          id="tx-method"
          className={styles.select}
          value={draft.payment_method}
          onChange={(event) => onChange({ payment_method: event.target.value })}
        >
          {METHOD_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <label className={styles.fieldLabel} htmlFor="tx-gateway">
          Gateway
        </label>
        <select
          id="tx-gateway"
          className={styles.select}
          value={draft.gateway}
          onChange={(event) => onChange({ gateway: event.target.value })}
        >
          {GATEWAY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <label className={styles.fieldLabel} htmlFor="tx-attempted-from">
          From
        </label>
        <input
          id="tx-attempted-from"
          className={styles.dateInput}
          type="date"
          value={draft.attempted_from}
          onChange={(event) => onChange({ attempted_from: event.target.value })}
        />
      </div>

      <div className={styles.field}>
        <label className={styles.fieldLabel} htmlFor="tx-attempted-to">
          To
        </label>
        <input
          id="tx-attempted-to"
          className={styles.dateInput}
          type="date"
          value={draft.attempted_to}
          onChange={(event) => onChange({ attempted_to: event.target.value })}
        />
      </div>

      <div className={styles.actions}>
        <Button variant="primary" size="sm" type="submit">
          Apply
        </Button>
        <Button variant="ghost" size="sm" type="button" onClick={onClear} disabled={!hasDraft}>
          Clear
        </Button>
      </div>
    </form>
  );
}