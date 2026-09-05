import { Button } from '@/components';

import { isValidTransactionId, type AppliedFilters } from '../constants';

import styles from './FilterBar.module.css';

interface FilterBarProps {
  draft: AppliedFilters;
  onChange: (changes: Partial<AppliedFilters>) => void;
  onApply: () => void;
  onClear: () => void;
}

export function FilterBar({ draft, onChange, onApply, onClear }: FilterBarProps) {
  const hasDraft = draft.transactionId.trim() !== '';
  const valid = isValidTransactionId(draft.transactionId);

  return (
    <form
      className={styles.bar}
      onSubmit={(event) => {
        event.preventDefault();
        if (valid) {
          onApply();
        }
      }}
    >
      <div className={styles.field}>
        <label className={styles.fieldLabel} htmlFor="audit-transaction">
          Transaction ID
        </label>
        <input
          id="audit-transaction"
          className={styles.input}
          type="text"
          inputMode="numeric"
          placeholder="Filter events by transaction id"
          value={draft.transactionId}
          aria-invalid={!valid}
          onChange={(event) => onChange({ transactionId: event.target.value })}
        />
        {!valid && (
          <span className={styles.hint}>Enter a positive integer transaction id.</span>
        )}
      </div>

      <div className={styles.actions}>
        <Button variant="primary" size="sm" type="submit" disabled={!valid}>
          Apply
        </Button>
        <Button
          variant="ghost"
          size="sm"
          type="button"
          onClick={onClear}
          disabled={!hasDraft}
        >
          Clear
        </Button>
      </div>
    </form>
  );
}