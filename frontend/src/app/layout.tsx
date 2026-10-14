import { ClientErrorMonitor } from '@/components/client-error-monitor';
import type { Metadata } from 'next';
import './globals.css';
import './dashboard.css';
export const metadata: Metadata = { title: 'Stride', description: 'Read with focus. Practise with purpose.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body className="antialiased"><ClientErrorMonitor />{children}</body></html>;
}
