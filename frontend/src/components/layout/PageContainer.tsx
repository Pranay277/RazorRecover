import type { ReactNode } from 'react';

import styles from './PageContainer.module.css';

export function PageContainer({ children }: { children?: ReactNode }) {
  return <div className={styles.container}>{children}</div>;
}