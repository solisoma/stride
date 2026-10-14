"use client";
import { useEffect } from 'react';
import { logger } from '@/utils/logger';
export function ClientErrorMonitor() {
  useEffect(() => {
    const error = (event: ErrorEvent) => logger.error('browser_error', { errorType: event.error?.name || 'Error', line: event.lineno, column: event.colno });
    const rejection = (event: PromiseRejectionEvent) => logger.error('unhandled_rejection', { errorType: event.reason instanceof Error ? event.reason.name : 'Unknown' });
    window.addEventListener('error', error);
    window.addEventListener('unhandledrejection', rejection);
    return () => { window.removeEventListener('error', error); window.removeEventListener('unhandledrejection', rejection); };
  }, []);
  return null;
}
