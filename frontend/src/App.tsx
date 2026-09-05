import { Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from '@/components';
import {
  AuditLogs,
  RecoveryCommandCenter,
  TransactionDetails,
  TransactionsInvestigation,
} from '@/pages';

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<RecoveryCommandCenter />} />
        <Route path="transactions" element={<TransactionsInvestigation />} />
        <Route path="transactions/:transactionId" element={<TransactionDetails />} />
        <Route path="audit" element={<AuditLogs />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}