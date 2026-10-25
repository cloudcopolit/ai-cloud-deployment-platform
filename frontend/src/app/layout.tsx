import type { Metadata } from 'next'
import { ThemeProvider } from '@/components/app/theme'
import { Toaster } from '@/components/ui/sonner'
import './globals.css'

export const metadata: Metadata = {
  title: { default: 'CloudPilot', template: '%s · CloudPilot' },
  description: 'From a GitHub repository to a reviewed, human-approved AWS deployment.'
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:shadow"
        >
          Skip to content
        </a>
        <ThemeProvider>
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  )
}
