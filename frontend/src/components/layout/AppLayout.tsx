import { Outlet } from 'react-router-dom';

import { Header } from './Header';
import { PageContainer } from './PageContainer';
import { Sidebar } from './Sidebar';

import styles from './AppLayout.module.css';

export function AppLayout() {
  return (
    <div className={styles.shell}>
      <Sidebar />
      <div className={styles.main}>
        <Header />
        <div className={styles.content}>
          <PageContainer>
            <Outlet />
          </PageContainer>
        </div>
      </div>
    </div>
  );
}