import { useState } from 'react';
import { Link } from 'react-router-dom';

import {
  StatusBadge,
  Table,
  TBody,
  TCell,
  THead,
  THeadCell,
  TRow,
  type BadgeTone,
} from '@/components';
import { executionStatusBadge, formatDateTimeCompact, humanizeAction, shieldBadge } from '@/utils';
import type { AuditLogItem } from '@/types';

import { AuditLogDetail } from './AuditLogDetail';

import styles from './AuditLogsTable.module.css';

interface AuditLogsTableProps {
  items: AuditLogItem[];
}

function actorBadge(actor: string | null): { label: string; tone: BadgeTone } {
  const value = actor ?? 'unknown';
  const lower = value.toLowerCase();
  let tone: BadgeTone = 'neutral';
  if (lower.includes('recovery')) {
    tone = 'success';
  } else if (lower.includes('merchant') || lower.includes('api')) {
    tone = 'info';
  }
  return { label: value, tone };
}

export function AuditLogsTable({ items }: AuditLogsTableProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const toggle = (id: number) => {
    setExpandedId((current) => (current === id ? null : id));
  };

  return (
    <Table>
      <THead>
        <tr>
          <THeadCell>Time</THeadCell>
          <THeadCell>Transaction</THeadCell>
          <THeadCell>Actor</THeadCell>
          <THeadCell>Action</THeadCell>
          <THeadCell>Requested AI Action</THeadCell>
          <THeadCell>Policy Decision</THeadCell>
          <THeadCell>Execution</THeadCell>
          <THeadCell className={styles.chevronHead} aria-hidden="true" />
        </tr>
      </THead>
      <TBody>
        {items.map((event) => (
          <EventRows
            key={event.id}
            event={event}
            expanded={expandedId === event.id}
            onToggle={toggle}
          />
        ))}
      </TBody>
    </Table>
  );
}

interface EventRowsProps {
  event: AuditLogItem;
  expanded: boolean;
  onToggle: (id: number) => void;
}

function EventRows({ event, expanded, onToggle }: EventRowsProps) {
  const policy = event.policy_decision;
  const execution = event.execution_status;
  const aiAction = event.llm_requested_action;

  return (
    <>
      <TRow onClick={() => onToggle(event.id)}>
        <TCell mono>{formatDateTimeCompact(event.occurred_at)}</TCell>
        <TCell>
          {event.transaction_id !== null ? (
            <Link
              to={`/transactions/${event.transaction_id}`}
              className={styles.txLink}
              onClick={(e) => e.stopPropagation()}
              title={`Open transaction ${event.transaction_id}`}
            >
              <span className={styles.txId}>
                {event.transaction_external_id ?? `#${event.transaction_id}`}
              </span>
              <svg
                className={styles.linkIcon}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M7 17 17 7M7 7h10v10" />
              </svg>
            </Link>
          ) : (
            '—'
          )}
        </TCell>
        <TCell>
          <StatusBadge {...actorBadge(event.actor)} />
        </TCell>
        <TCell>
          <span className={styles.action}>{event.action}</span>
        </TCell>
        <TCell>{aiAction ? <span className={styles.aiChip}>{humanizeAction(aiAction)}</span> : '—'}</TCell>
        <TCell>{policy ? <StatusBadge {...shieldBadge(policy)} /> : '—'}</TCell>
        <TCell>{execution ? <StatusBadge {...executionStatusBadge(execution)} /> : '—'}</TCell>
        <TCell className={styles.chevronCell}>
          <svg
            className={`${styles.chevron} ${expanded ? styles.chevronOpen : ''}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
        </TCell>
      </TRow>
      {expanded && (
        <tr className={styles.detailRow}>
          <td colSpan={8} className={styles.detailCell}>
            <AuditLogDetail event={event} />
          </td>
        </tr>
      )}
    </>
  );
}