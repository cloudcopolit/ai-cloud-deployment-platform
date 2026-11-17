import type { Metadata, Viewport } from 'next'
import { Rajdhani } from 'next/font/google'
import { ThemeProvider } from '@/components/app/theme'
import { Toaster } from '@/components/ui/sonner'
import './globals.css'

/* Self-hosted at build time by next/font: no request to Google from the browser. */
/* Rajdhani ships 300–700; only the weights the UI uses are loaded. */
const rajdhani = Rajdhani({
  subsets: ['latin-ext', 'latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-rajdhani',
  display: 'swap'
})

export const metadata: Metadata = {
  title: { default: 'CloudPilot', template: '%s · CloudPilot' },
  description:
    'CloudPilot reads your GitHub repository, explains what it found, and has AI agents propose an AWS architecture you review and approve.',
  applicationName: 'CloudPilot'
}

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#000000' }
  ]
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={rajdhani.variable}>
      <body className="min-h-screen bg-background antialiased">
        <ThemeProvider>
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  )
}
