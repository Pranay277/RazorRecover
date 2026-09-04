import { Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from '@/components';
import { PlaceholderPage } from '@/pages';

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route
          index
          element={
            <PlaceholderPage
              title="Overview"
              description="Recovery Command Center metrics and drill-downs will be implemented here."
            />
          }
        />
        <Route
          path="transactions"
          element={
            <PlaceholderPage
              title="Transactions"
              description="The failed-payments investigation table will be implemented here."
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
              title="Audit Logs"
              description="The audit trail for recovery decisions and executions will be implemented here."
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}