import Link from 'next/link'
import { ShieldCheck, Zap, Activity, GitBranch } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import logo from '/public/logos/logo-icon.svg'
import Image from 'next/image'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const metadata = {
  title: 'Sign in — Cloud Copilot'
}

export default function LoginPage() {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      {/* ==================== LEFT — BRAND PANEL ==================== */}
      <aside className="relative hidden flex-col justify-between overflow-hidden border-r bg-muted/30 p-10 lg:flex">
        {/* Soft gradient orbs */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-24 -left-24 size-[380px] rounded-full bg-primary/20 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 -bottom-24 size-[300px] rounded-full bg-accent/20 blur-3xl"
        />

        {/* Grid overlay */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.04] [background-image:linear-gradient(to_right,currentColor_1px,transparent_1px),linear-gradient(to_bottom,currentColor_1px,transparent_1px)] [background-size:48px_48px] [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]"
        />

        {/* Brand mark */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-lg bg-gradient-to-br from-primary to-accent text-primary-foreground shadow-lg shadow-primary/25">
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
            <span className="bg-gradient-to-br from-primary to-accent bg-clip-text text-transparent">
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
