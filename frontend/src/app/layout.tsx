import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Flow — SME Finance Copilot',
  description: 'A live demo of an AI finance assistant for Thai SMEs.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
