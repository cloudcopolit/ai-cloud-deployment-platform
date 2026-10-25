import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Cloud Copilot',
  description: 'Your cloud, on autopilot.'
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">{children}</body>
    </html>
  )
}
