import Link from 'next/link'
import { Suspense } from 'react'
import { connection } from 'next/server'

import { TechLogo } from '@/components/brand/icons'
import { Logo } from '@/components/brand/logo'
import { Pipeline } from '@/components/brand/pipeline'
import { DevLogin } from './_components/dev-login'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const metadata = { title: 'Sign in' }

const ERROR_MESSAGES: Record<string, string> = {
  github_failed: 'GitHub sign-in failed. Please try again.',
  oauth_state: 'Your sign-in attempt expired. Please try again.',
  access_denied: 'You declined the GitHub authorization.'
}

export default function LoginPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  return (
    <div className="grid min-h-svh lg:grid-cols-[1.15fr_1fr]">
      {/* brand panel: `dark` keeps its text on the checked dark-theme tokens in either theme */}
      <aside className="dark relative hidden overflow-hidden bg-brand-black p-10 text-foreground lg:flex lg:flex-col lg:justify-between">
        <div aria-hidden className="bg-grid absolute inset-0 opacity-30" />
        <div aria-hidden className="absolute -left-32 -top-32 size-[32rem] rounded-full bg-brand-blue/30 blur-3xl" />
        <div aria-hidden className="absolute -bottom-40 -right-20 size-[26rem] rounded-full bg-brand-teal/20 blur-3xl" />
        <Link href="/" className="relative w-fit" aria-label="CloudPilot home">
          <Logo surface="dark" className="h-9" priority />
        </Link>
        <div className="relative max-w-2xl space-y-8">
          <div className="space-y-4">
            <h1 className="font-display text-4xl font-semibold leading-tight tracking-tight">
              From a GitHub repository to <span className="text-brand-gradient">a reviewed AWS deployment</span>.
            </h1>
            <p className="text-muted-foreground">
              AI agents analyze and propose. Only a person with the ADMIN or OWNER role can approve a change to your
              AWS account.
            </p>
          </div>
          <Pipeline showLevels={false} className="lg:grid-cols-3 xl:grid-cols-6" />
        </div>
        <p className="relative text-xs text-muted-foreground">
          Repository content is read as text and never executed.
        </p>
      </aside>

      <main id="main" className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-7">
          <div className="space-y-2">
            <Link href="/" className="mb-6 block w-fit lg:hidden" aria-label="CloudPilot home">
              <Logo className="h-8" priority />
            </Link>
            <h2 className="font-display text-2xl font-semibold tracking-tight">Sign in to CloudPilot</h2>
            <p className="text-sm text-muted-foreground">
              GitHub sign-in shares your public profile and email only. Repository access is granted separately.
            </p>
          </div>
          <Suspense fallback={null}>
            <LoginError searchParams={searchParams} />
          </Suspense>
          <a
            href={`${API_URL}/auth/github/login`}
            className="flex h-11 w-full items-center justify-center gap-2.5 rounded-xl bg-foreground px-4 text-sm font-medium text-background shadow-sm hover:bg-foreground/90"
          >
            <TechLogo name="github" label="" className="size-5" />
            Continue with GitHub
          </a>
          <Suspense fallback={null}>
            <DevLoginGate />
          </Suspense>
          <p className="text-xs text-muted-foreground">
            New here? <Link href="/" className="text-primary underline-offset-4 hover:underline">See how CloudPilot works</Link>.
          </p>
        </div>
      </main>
    </div>
  )
}

async function LoginError({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await searchParams
  if (!error) return null
  return (
    <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
      {ERROR_MESSAGES[error] ?? 'Sign-in failed. Please try again.'}
    </p>
  )
}

/** Read at request time (not inlined at build), so the same image works in every environment. */
async function DevLoginGate() {
  await connection()
  return process.env.DEV_LOGIN_ENABLED === 'true' ? <DevLogin /> : null
}
