import type { Metadata, Viewport } from 'next'
import { Inter, Poppins } from 'next/font/google'
import { ThemeProvider } from '@/components/app/theme'
import { Toaster } from '@/components/ui/sonner'
import './globals.css'

/* Self-hosted at build time by next/font: no request to Google from the browser. */
const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' })
const poppins = Poppins({
  subsets: ['latin'],
  weight: ['500', '600', '700'],
  variable: '--font-poppins',
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
    { media: '(prefers-color-scheme: dark)', color: '#0b1220' }
  ]
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${poppins.variable}`}>
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
