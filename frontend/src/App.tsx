import { Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from '@/components';
import {
  PlaceholderPage,
  RecoveryCommandCenter,
  TransactionsInvestigation,
} from '@/pages';

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<RecoveryCommandCenter />} />
        <Route path="transactions" element={<TransactionsInvestigation />} />
        <Route
          path="transaction-details"
          element={
            <PlaceholderPage
              title="Transaction Details"
              description="The full persisted view of a single transaction will be implemented here."
            />
          }
        />
        <Route
          path="transactions/:transactionId"
          element={
            <PlaceholderPage
              title="Transaction Details"
              description="The full persisted view of a single transaction will be implemented here."
            />
          }
        />
        <Route
          path="audit"
          element={
            <PlaceholderPage
              title="Audit logs"
              description="The audit trail for recovery decisions and executions will be implemented here."
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}