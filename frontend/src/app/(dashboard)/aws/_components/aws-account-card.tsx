'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Check, Copy, Download, ShieldCheck, X } from 'lucide-react'

import { ErrorState } from '@/components/app/states'
import { TechLogo } from '@/components/brand/icons'
import { Button } from '@/components/ui/button'
import { apiFetch } from '@/lib/api/client'
import type { ApiFailure } from '@/lib/api/result'
import { AwsAccountSchema, OnboardingSchema, type AwsAccount, type Onboarding } from '@/lib/api/schemas'
import { formatRelative } from '@/lib/format'
import { cn } from '@/lib/utils'

const STATUS: Record<string, { label: string; className: string }> = {
  ACTIVE: { label: 'Verified', className: 'border-success/50 text-success' },
  PENDING_VERIFICATION: { label: 'Waiting for the onboarding stack', className: 'border-warning/60 text-warning' },
  VERIFICATION_FAILED: { label: 'Verification failed', className: 'border-destructive/50 text-destructive' },
  DISCONNECTED: { label: 'Disconnected', className: 'border-border-strong text-muted-foreground' }
}

function CopyValue({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="flex items-center gap-1.5">
        <code className="min-w-0 truncate font-mono text-xs">{value}</code>
        <button
          type="button"
          className="shrink-0 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label={`Copy ${label}`}
          onClick={() => {
            void navigator.clipboard?.writeText(value)
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
          }}
        >
          {copied ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
        </button>
      </dd>
    </div>
  )
}

function Evidence({ ok, children }: { ok: boolean | null; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2 text-sm">
      {ok ? (
        <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
      ) : (
        <X className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
      )}
      <span>
        <span className="sr-only">{ok ? 'Passed: ' : 'Not passed: '}</span>
        {children}
      </span>
    </li>
  )
}

/** One connected AWS account: onboarding template, then a real STS verification. */
export function AwsAccountCard({ account: initial, canAdmin }: { account: AwsAccount; canAdmin: boolean }) {
  const router = useRouter()
  const [account, setAccount] = useState(initial)
  const [onboarding, setOnboarding] = useState<Onboarding | null>(null)
  const [busy, setBusy] = useState<'template' | 'verify' | null>(null)
  const [failure, setFailure] = useState<ApiFailure | null>(null)
  const status = STATUS[account.status] ?? { label: account.status, className: '' }

  async function loadTemplate(download: boolean) {
    setBusy('template')
    setFailure(null)
    const res = await apiFetch(`/aws-accounts/${account.id}/onboarding`, OnboardingSchema)
    setBusy(null)
    if (!res.ok) return setFailure(res)
    setOnboarding(res.data)
    if (download) {
      const url = URL.createObjectURL(new Blob([res.data.template], { type: 'application/json' }))
      const a = document.createElement('a')
      a.href = url
      a.download = 'cloudpilot-onboarding.json'
      a.click()
      URL.revokeObjectURL(url)
    }
  }

  async function verify() {
    setBusy('verify')
    setFailure(null)
    const res = await apiFetch(`/aws-accounts/${account.id}/verify`, AwsAccountSchema, { method: 'POST' })
    setBusy(null)
    if (!res.ok) return setFailure(res)
    setAccount(res.data)
    router.refresh()
  }

  return (
    <li className="space-y-4 rounded-2xl border bg-card p-5" aria-label={`AWS account ${account.aws_account_id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid size-11 place-items-center rounded-xl bg-icon-surface">
            <TechLogo name="aws" label="" className="size-7" />
          </span>
          <div>
            <p className="font-display text-lg font-semibold">Account {account.aws_account_id}</p>
            <p className="text-xs text-muted-foreground">
              {account.default_region} · connected {formatRelative(account.connected_at)}
              {account.last_verified_at ? ` · verified ${formatRelative(account.last_verified_at)}` : ''}
            </p>
          </div>
        </div>
        <span className={cn('rounded-full border px-2.5 py-0.5 text-xs font-medium', status.className)}>
          {status.label}
        </span>
      </div>

      <dl className="grid gap-3 sm:grid-cols-2">
        <CopyValue label="External ID (per account, not a secret)" value={account.external_id} />
        {account.role_arn ? <CopyValue label="Deploy role CloudPilot assumes" value={account.role_arn} /> : null}
        {account.state_bucket ? <CopyValue label="State bucket (in your account)" value={account.state_bucket} /> : null}
        {account.onboarding_stack ? <CopyValue label="CloudFormation stack" value={account.onboarding_stack} /> : null}
      </dl>

      {account.status !== 'ACTIVE' ? (
        <ol className="space-y-2 rounded-xl bg-muted/60 p-4 text-sm">
          <li>
            <span className="font-medium">1.</span> Download the onboarding template. It creates the deploy role (trusted
            only by CloudPilot, only with this External ID), its permission boundary and an encrypted state bucket.
          </li>
          <li>
            <span className="font-medium">2.</span> Deploy it in this account (CloudFormation console, or the CLI command).
          </li>
          <li>
            <span className="font-medium">3.</span> Verify: CloudPilot calls STS AssumeRole with the External ID and checks
            that the role cannot be assumed without it.
          </li>
        </ol>
      ) : null}

      {onboarding ? (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Deploy with the AWS CLI</p>
          <pre className="overflow-x-auto rounded-lg bg-black p-3 font-mono text-xs text-zinc-200 ring-1 ring-white/10">
            {onboarding.cli_command}
          </pre>
          <p className="text-xs text-muted-foreground">
            CloudPilot&apos;s principal: <code className="font-mono">{onboarding.platform_principal_arn}</code>
          </p>
        </div>
      ) : null}

      {account.verification_message ? (
        <ul className="space-y-1.5 rounded-xl border p-4" aria-label="Last verification">
          <Evidence ok={account.status === 'ACTIVE'}>
            STS AssumeRole with the External ID{' '}
            {account.verified_identity_arn ? (
              <code className="break-all font-mono text-xs">{account.verified_identity_arn}</code>
            ) : (
              <span className="text-muted-foreground">({account.verification_message})</span>
            )}
          </Evidence>
          <Evidence ok={account.external_id_enforced}>AssumeRole without the External ID is denied</Evidence>
          <Evidence ok={account.status === 'ACTIVE'}>State bucket reachable with the role</Evidence>
        </ul>
      ) : null}

      {failure ? <ErrorState failure={failure} /> : null}

      {canAdmin ? (
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={() => loadTemplate(true)} disabled={busy !== null}>
            <Download className="size-4" aria-hidden />
            {busy === 'template' ? 'Preparing…' : 'Download onboarding template'}
          </Button>
          <Button type="button" variant="outline" onClick={() => loadTemplate(false)} disabled={busy !== null}>
            Show CLI command
          </Button>
          <Button type="button" onClick={verify} disabled={busy !== null}>
            <ShieldCheck className="size-4" aria-hidden />
            {busy === 'verify' ? 'Verifying with AWS STS…' : account.status === 'ACTIVE' ? 'Verify again' : 'Verify connection'}
          </Button>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">Only an ADMIN or OWNER can change this connection.</p>
      )}
    </li>
  )
}
