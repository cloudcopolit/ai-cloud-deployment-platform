import Image from 'next/image'
import { Suspense } from 'react'
import { connection } from 'next/server'
import { GitBranch } from 'lucide-react'

import logo from '/public/logos/logo-icon.svg'
import { DevLogin } from './_components/dev-login'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const metadata = { title: 'Sign in' }

const ERROR_MESSAGES: Record<string, string> = {
  github_failed: 'GitHub sign-in failed. Please try again.',
  oauth_state: 'Your sign-in attempt expired. Please try again.',
  access_denied: 'You declined the GitHub authorization.'
}

/* What the product does today, stated plainly. Capability status lives in WORKLOG/HANDOFF. */
const STEPS = [
  'Connect a GitHub repository',
  'Analyze it: languages, services, dependencies, risks',
  'Review a proposed AWS architecture with cost',
  'Approve a Terraform plan before anything changes in AWS'
]

export default function LoginPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <aside className="hidden flex-col justify-between border-r bg-muted/40 p-10 lg:flex">
        <div className="flex items-center gap-2.5">
          <Image src={logo} alt="" className="size-9" />
          <span className="text-lg font-semibold tracking-tight">CloudPilot</span>
        </div>
        <div className="max-w-md space-y-5">
          <h1 className="text-3xl font-semibold tracking-tight">
            From a GitHub repository to a reviewed AWS deployment.
          </h1>
          <ol className="space-y-2 text-muted-foreground">
            {STEPS.map((step, i) => (
              <li key={step} className="flex gap-3">
                <span className="font-mono text-primary">{i + 1}.</span>
                {step}
              </li>
            ))}
          </ol>
          <p className="text-sm text-muted-foreground">
            AI analyzes and proposes. Only a person with the ADMIN or OWNER role can approve a change
            to your AWS account.
          </p>
        </div>
        <p className="text-xs text-muted-foreground">Graduation project · not production-ready</p>
      </aside>

      <main id="main" className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-6">
          <div className="space-y-1 text-center">
            <Image src={logo} alt="" className="mx-auto mb-3 size-10 lg:hidden" />
            <h2 className="text-2xl font-semibold tracking-tight">Sign in</h2>
            <p className="text-sm text-muted-foreground">
              GitHub sign-in shares your public profile and email only. Repository access is
              granted separately.
            </p>
          </div>
          <Suspense fallback={null}>
            <LoginError searchParams={searchParams} />
          </Suspense>
          <a
            href={`${API_URL}/auth/github/login`}
            className="flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <GitBranch className="size-4" aria-hidden />
            Continue with GitHub
          </a>
          <Suspense fallback={null}>
            <DevLoginGate />
          </Suspense>
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
