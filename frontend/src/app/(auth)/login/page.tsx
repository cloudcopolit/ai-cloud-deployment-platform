import Link from 'next/link'
import { ShieldCheck, Zap, Activity, GitBranch, AlertCircle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import logo from '/public/logos/logo-icon.svg'
import Image from 'next/image'
import { Suspense } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const metadata = { title: 'Sign in — CloudPilot' }

export default async function LoginPage({
  searchParams
}: {
  searchParams: Promise<{ error?: string }>
}) {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      {/* ==================== LEFT — BRAND PANEL ==================== */}
      <aside className="relative hidden flex-col justify-between overflow-hidden border-r bg-muted/30 p-10 lg:flex">
        {/* Soft gradient orbs */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-24 -left-24 size-95 rounded-full bg-primary/20 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 -bottom-24 size-75 rounded-full bg-accent/20 blur-3xl"
        />

        {/* Grid overlay */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.04] bg-[linear-gradient(to_right,currentColor_1px,transparent_1px),linear-gradient(to_bottom,currentColor_1px,transparent_1px)] bg-size-[48px_48px] mask-[radial-gradient(ellipse_at_center,black_30%,transparent_75%)]"
        />

        {/* Brand mark */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-lg bg-linear-to-br from-primary to-accent text-primary-foreground shadow-lg shadow-primary/25">
            <Image src={logo} alt="Cloud Copilot logo" className="size-5" />
          </div>
          <span className="text-lg font-semibold tracking-tight">
            Cloud <span className="font-normal text-muted-foreground">Copilot</span>
          </span>
        </div>

        {/* Hero */}
        <div className="relative z-10 max-w-md space-y-6">
          <h1 className="text-4xl font-bold tracking-tight">
            Your cloud,{' '}
            <span className="bg-linear-to-br from-primary to-accent bg-clip-text text-transparent">
              on autopilot.
            </span>
          </h1>
          <p className="text-muted-foreground">
            Deploy, monitor, and scale infrastructure with an AI copilot that understands your
            stack. Ship faster with fewer incidents.
          </p>

          <ul className="space-y-3 text-sm text-muted-foreground">
            <li className="flex items-center gap-3">
              <Zap className="size-4 shrink-0 text-primary" />
              Instant deployments across 30+ regions
            </li>
            <li className="flex items-center gap-3">
              <ShieldCheck className="size-4 shrink-0 text-primary" />
              SOC 2 Type II &amp; HIPAA compliant
            </li>
            <li className="flex items-center gap-3">
              <Activity className="size-4 shrink-0 text-primary" />
              Real-time observability &amp; alerting
            </li>
          </ul>
        </div>

        {/* Footer */}
        <p className="relative z-10 font-mono text-xs text-muted-foreground/70">
          © 2026 Cloud Copilot, Inc.
        </p>
      </aside>

      {/* ==================== RIGHT — AUTH FORM ==================== */}
      <main className="flex items-center justify-center p-6 lg:p-10">
        <Card className="w-full max-w-sm border-border/60 shadow-xl">
          <CardHeader className="space-y-2 text-center">
            {/* Mobile brand */}
            <div className="mx-auto mb-2 grid size-10 place-items-center rounded-lg bg-linear-to-br from-primary to-accent text-primary-foreground lg:hidden">
              <Image src={logo} alt="Cloud Copilot logo" className="size-5" />
            </div>
            <CardTitle className="text-2xl tracking-tight">Welcome back</CardTitle>
            <CardDescription>Sign in to your Cloud Copilot workspace</CardDescription>
          </CardHeader>

          <CardContent className="space-y-6">
            {/* Dynamic part — reads ?error= from searchParams */}
            <Suspense fallback={null}>
              <LoginErrorBanner searchParams={searchParams} />
            </Suspense>
            {/* GitHub login — plain anchor to FastAPI */}
            <Button asChild size="lg" className="w-full">
              <Link href={`${API_URL}/auth/github/login`}>
                <GitBranch className="size-4" />
                Continue with GitHub
              </Link>
            </Button>

            {/* Divider */}
            <div className="relative">
              <Separator />
              <span className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-card px-2 text-xs text-muted-foreground">
                Secure sign-in
              </span>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Dynamic child — awaits searchParams                                 */
/*  Isolated in Suspense so the static shell renders immediately.       */
/* ------------------------------------------------------------------ */
const ERROR_MESSAGES: Record<string, string> = {
  github_failed: 'GitHub sign-in failed. Please try again.',
  oauth_state: 'Your session expired. Please try again.',
  access_denied: 'You declined the GitHub authorization.'
}

async function LoginErrorBanner({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await searchParams
  if (!error) return null

  const message = ERROR_MESSAGES[error] ?? 'Sign-in failed. Please try again.'

  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive-foreground"
    >
      <AlertCircle className="mt-0.5 size-4 shrink-0" />
      <span>{message}</span>
    </div>
  )
}
