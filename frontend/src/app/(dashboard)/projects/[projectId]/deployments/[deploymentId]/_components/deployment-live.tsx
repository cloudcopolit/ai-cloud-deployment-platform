'use client'

import { useCallback, useState } from 'react'
import { Check, ChevronRight, ExternalLink, Loader2, Minus, X } from 'lucide-react'

import { AgentPortrait } from '@/components/agents/agent-avatar'
import { ErrorState } from '@/components/app/states'
import { SpriteIcon } from '@/components/brand/icons'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { AGENTS } from '@/lib/agents'
import { apiFetch } from '@/lib/api/client'
import type { ApiFailure } from '@/lib/api/result'
import {
  ApprovalSchema,
  AuditEntrySchema,
  DeploymentSchema,
  type AuditEntry,
  type Deployment,
  type DeployStep
} from '@/lib/api/schemas'
import { formatDuration, formatUsd } from '@/lib/format'
import { useNow } from '@/lib/use-now'
import { usePoll } from '@/lib/use-poll'
import { cn } from '@/lib/utils'

const ACTIVE = new Set(['QUEUED', 'PLANNING', 'APPLY_QUEUED', 'APPLYING', 'VERIFYING', 'DESTROY_QUEUED', 'DESTROYING'])
const DESTROYABLE = new Set(['SUCCESS', 'FAILED', 'TIMED_OUT', 'DESTROY_FAILED'])

const STATUS: Record<string, { label: string; sentence: string; tone: 'info' | 'ok' | 'warn' | 'bad' | 'muted' }> = {
  QUEUED: { label: 'Queued', sentence: 'Waiting for the deploy runner to plan.', tone: 'info' },
  PLANNING: { label: 'Planning', sentence: 'OpenTofu is planning in your account.', tone: 'info' },
  AWAITING_APPROVAL: { label: 'Awaiting approval', sentence: 'The plan is ready. An ADMIN or OWNER must approve this exact plan.', tone: 'warn' },
  BLOCKED: { label: 'Blocked by policy', sentence: 'The plan breaks a policy and cannot be approved.', tone: 'bad' },
  APPLY_QUEUED: { label: 'Apply queued', sentence: 'Approved. Waiting for the deploy runner to apply.', tone: 'info' },
  APPLYING: { label: 'Applying', sentence: 'OpenTofu is creating the resources (RDS takes several minutes).', tone: 'info' },
  VERIFYING: { label: 'Checking health', sentence: 'Waiting for ECS and calling the health route over HTTP.', tone: 'info' },
  SUCCESS: { label: 'Live', sentence: 'Deployed, and the health check passed.', tone: 'ok' },
  FAILED: { label: 'Failed', sentence: 'The deployment failed; see the failed step.', tone: 'bad' },
  TIMED_OUT: { label: 'Timed out', sentence: 'The runner stopped responding; infrastructure may exist.', tone: 'bad' },
  CANCELLED: { label: 'Rejected', sentence: 'The plan was rejected. Nothing was created.', tone: 'muted' },
  DESTROY_QUEUED: { label: 'Destroy queued', sentence: 'Waiting for the deploy runner to destroy.', tone: 'info' },
  DESTROYING: { label: 'Destroying', sentence: 'OpenTofu is deleting everything it created.', tone: 'info' },
  DESTROYED: { label: 'Destroyed', sentence: 'Everything was deleted, and no tagged resource remains.', tone: 'ok' },
  DESTROY_FAILED: { label: 'Destroy incomplete', sentence: 'Some resources remain; retry destroy.', tone: 'bad' }
}

const TONE = {
  info: 'border-info/50 text-info',
  ok: 'border-success/50 text-success',
  warn: 'border-warning/60 text-warning',
  bad: 'border-destructive/50 text-destructive',
  muted: 'border-border-strong text-muted-foreground'
}

const STEP_COPY: Record<string, { title: string; icon: `ui-${string}` }> = {
  PLAN: { title: 'Plan with OpenTofu', icon: 'ui-file-code' },
  POLICY_CHECK: { title: 'Check the plan against policy', icon: 'ui-shield-check' },
  APPROVAL: { title: 'Human approval of the exact plan', icon: 'ui-user-check' },
  APPLY: { title: 'Apply the approved plan', icon: 'ui-rocket' },
  HEALTH_CHECK: { title: 'Real HTTP health check', icon: 'ui-activity' },
  DESTROY: { title: 'Destroy', icon: 'ui-trash' },
  VERIFY_CLEAN: { title: 'Prove nothing tagged remains', icon: 'ui-search' }
}

function Badge({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, tone: 'muted' as const }
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium', TONE[s.tone])}>
      {ACTIVE.has(status) ? <Loader2 className="size-3 animate-spin" aria-hidden /> : null}
      {s.label}
    </span>
  )
}

function StepIcon({ status }: { status: string }) {
  const base = 'grid size-6 place-items-center rounded-full border bg-background'
  if (status === 'RUNNING')
    return (
      <span className={cn(base, 'border-primary/60 text-primary')}>
        <Loader2 className="size-3.5 animate-spin" aria-hidden />
      </span>
    )
  if (status === 'SUCCESS')
    return (
      <span className={cn(base, 'border-success/50 bg-success/10 text-success')}>
        <Check className="size-3.5" aria-hidden />
      </span>
    )
  if (status === 'FAILED')
    return (
      <span className={cn(base, 'border-destructive/60 bg-destructive/10 text-destructive')}>
        <X className="size-3.5" aria-hidden />
      </span>
    )
  if (status === 'SKIPPED')
    return (
      <span className={cn(base, 'text-muted-foreground')}>
        <Minus className="size-3.5" aria-hidden />
      </span>
    )
  return <span className={cn(base, 'border-dashed border-border-strong')} />
}

function StepRow({ step, now, last }: { step: DeployStep; now: number; last: boolean }) {
  const [open, setOpen] = useState(step.status === 'FAILED')
  const copy = STEP_COPY[step.step_type] ?? { title: step.step_type, icon: 'ui-workflow' as const }
  const running = step.status === 'RUNNING'
  const started = step.started_at ? Date.parse(step.started_at) : null
  const ended = step.completed_at ? Date.parse(step.completed_at) : running ? now : null
  const duration = started && ended ? ended - started : null
  const out = step.output_data ?? {}
  const tail = Array.isArray(out.log_tail) ? (out.log_tail as string[]) : []
  const expandable = Boolean(tail.length || step.error_message || Object.keys(out).length)
  return (
    <li className="relative pl-9">
      {!last ? <span aria-hidden className="absolute bottom-[-0.75rem] left-3 top-7 w-px bg-border" /> : null}
      <span className="absolute left-0 top-0.5">
        <StepIcon status={step.status} />
      </span>
      <button
        type="button"
        disabled={!expandable}
        aria-expanded={expandable ? open : undefined}
        onClick={() => setOpen((v) => !v)}
        className="-mx-2 flex w-[calc(100%+1rem)] items-center gap-2 rounded-md px-2 py-1 text-left enabled:hover:bg-muted/60"
      >
        <SpriteIcon name={copy.icon} className="size-4 text-muted-foreground" />
        <span className={cn('min-w-0 truncate text-sm', running && 'shimmer-text font-medium', step.status === 'FAILED' && 'font-medium text-destructive', (step.status === 'QUEUED' || step.status === 'SKIPPED') && 'text-muted-foreground')}>
          {copy.title}
          {running ? '…' : ''}
        </span>
        <span className="sr-only">({step.status.toLowerCase()})</span>
        <span className="ml-auto shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
          {duration !== null ? formatDuration(duration) : step.status === 'SKIPPED' ? 'skipped' : ''}
        </span>
        {expandable ? <ChevronRight className={cn('size-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-90')} aria-hidden /> : <span className="size-4" />}
      </button>
      {step.error_message && !open ? (
        <p className="mt-0.5 text-xs text-destructive">
          {step.error_code}: {step.error_message}
        </p>
      ) : null}
      {open ? (
        <div className="mt-2 overflow-x-auto rounded-lg bg-black p-3 font-mono text-xs leading-relaxed text-zinc-200 ring-1 ring-white/10">
          <p className="text-zinc-400">
            $ {step.step_type.toLowerCase()} · {step.status.toLowerCase()}
          </p>
          {tail.map((line, i) => (
            <p key={i} className="whitespace-pre-wrap break-words">
              {line}
            </p>
          ))}
          {!tail.length ? (
            <pre className="whitespace-pre-wrap break-words">{JSON.stringify(out, null, 2)}</pre>
          ) : null}
          {step.error_message ? (
            <p className="mt-2 text-red-300">
              ✕ {step.error_code}: {step.error_message}
            </p>
          ) : null}
        </div>
      ) : null}
    </li>
  )
}

function Card({ title, children, className, id }: { title: string; children: React.ReactNode; className?: string; id?: string }) {
  const headingId = id ?? title.toLowerCase().replaceAll(/[^a-z]+/g, '-')
  return (
    <section aria-labelledby={headingId} className={cn('space-y-3 rounded-2xl border bg-card p-4 sm:p-5', className)}>
      <h2 id={headingId} className="font-semibold">
        {title}
      </h2>
      {children}
    </section>
  )
}

export function DeploymentLive({
  initial,
  initialAudit,
  canAdmin
}: {
  initial: Deployment
  initialAudit: AuditEntry[]
  canAdmin: boolean
}) {
  const [d, setD] = useState(initial)
  const [audit, setAudit] = useState(initialAudit)
  const [failure, setFailure] = useState<ApiFailure | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [reviewed, setReviewed] = useState(false)
  const [confirm, setConfirm] = useState('')
  const active = ACTIVE.has(d.status)
  const now = useNow(active)

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      const [dep, trail] = await Promise.all([
        apiFetch(`/deployments/${d.id}`, DeploymentSchema, { signal }),
        apiFetch(`/deployments/${d.id}/audit`, AuditEntrySchema.array(), { signal })
      ])
      if (!dep.ok) {
        setFailure(dep)
        return { done: false, changed: false }
      }
      setFailure(null)
      const changed = dep.data.status !== d.status || JSON.stringify(dep.data.steps) !== JSON.stringify(d.steps)
      setD(dep.data)
      if (trail.ok) setAudit(trail.data)
      return { done: !ACTIVE.has(dep.data.status), changed }
    },
    [d.id, d.status, d.steps]
  )
  usePoll(refresh, { enabled: active })

  async function act(name: string, path: string, body?: unknown) {
    setBusy(name)
    setFailure(null)
    const res =
      name === 'approve' || name === 'reject'
        ? await apiFetch(path, ApprovalSchema, { method: 'POST', body })
        : await apiFetch(path, DeploymentSchema, { method: 'POST', body })
    setBusy(null)
    if (!res.ok) return setFailure(res)
    await refresh()
  }

  const status = STATUS[d.status] ?? { label: d.status, sentence: '', tone: 'muted' as const }
  const done = d.steps.filter((s) => s.status === 'SUCCESS' || s.status === 'SKIPPED').length
  const started = d.started_at ? Date.parse(d.started_at) : null
  const approved = d.approval?.status === 'APPROVED' && d.approval.plan_hash === d.plan_hash
  const failedChecks = (d.policy_results ?? []).filter((c) => !c.passed)

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border bg-card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <AgentPortrait agent={AGENTS.DEPLOYMENT} size="sm" working={active} />
          <div className="min-w-0 flex-1">
            <p className={cn('text-sm font-medium', active && 'shimmer-text')} role="status" aria-live="polite">
              {status.sentence}
            </p>
            <p className="font-mono text-xs text-muted-foreground">
              image {d.image_uri?.split('@')[0]}@…{d.image_uri?.slice(-12)} · allowed {d.ingress_cidrs.join(', ')}
            </p>
          </div>
          {started ? (
            <span className="font-mono text-sm tabular-nums text-muted-foreground" title="Since the runner first started">
              {formatDuration((d.completed_at && !active ? Date.parse(d.completed_at) : now) - started)}
            </span>
          ) : null}
          <Badge status={d.status} />
        </div>
        <div
          role="progressbar"
          aria-label="Deployment steps finished"
          aria-valuemin={0}
          aria-valuemax={d.steps.length}
          aria-valuenow={done}
          className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted"
        >
          <div
            className={cn('h-full rounded-full transition-[width] duration-500', status.tone === 'bad' ? 'bg-destructive' : status.tone === 'ok' ? 'bg-success' : 'bg-brand-gradient')}
            style={{ width: `${Math.round((done / Math.max(1, d.steps.length)) * 100)}%` }}
          />
        </div>
      </div>

      {failure ? <ErrorState failure={failure} /> : null}
      {d.error_message ? (
        <div role="alert" className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm">
          <p className="font-medium text-destructive">{d.error_code}</p>
          <p>{d.error_message}</p>
        </div>
      ) : null}

      {d.status === 'SUCCESS' && d.live_endpoint ? (
        <section className="relative overflow-hidden rounded-2xl border border-success/50 bg-card p-5">
          <div aria-hidden className="absolute inset-x-0 top-0 h-1 bg-success" />
          <p className="font-display text-lg font-semibold">Your service is live</p>
          <a
            href={d.live_endpoint}
            target="_blank"
            rel="noreferrer"
            className="mt-1 inline-flex items-center gap-1.5 break-all font-mono text-sm text-primary underline-offset-4 hover:underline"
          >
            {d.live_endpoint} <ExternalLink className="size-3.5 shrink-0" aria-hidden />
          </a>
          <p className="mt-1 text-xs text-muted-foreground">Reachable only from {d.ingress_cidrs.join(', ')} (HTTP, no TLS yet).</p>
        </section>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <Card title="Steps">
          <ol aria-label="Deployment steps" className="space-y-3">
            {d.steps.map((s, i) => (
              <StepRow key={s.id} step={s} now={now} last={i === d.steps.length - 1} />
            ))}
          </ol>
        </Card>

        <div className="space-y-6">
          {d.status === 'AWAITING_APPROVAL' && d.plan_hash ? (
            <Card title={approved ? 'Approved: apply when ready' : 'Approve this exact plan'} id="approval" className="border-warning/60">
              <p className="text-sm text-muted-foreground">
                The approval is bound to the plan&apos;s SHA-256. If the plan changes, this approval stops counting.
              </p>
              <p className="break-all rounded-lg bg-muted p-2 font-mono text-xs" aria-label="Plan hash">
                {d.plan_hash}
              </p>
              {!canAdmin ? (
                <p className="text-sm text-muted-foreground">Only an ADMIN or OWNER can approve.</p>
              ) : approved ? (
                <>
                  <p className="text-xs text-muted-foreground">
                    Approved {d.approval?.decided_at ? new Date(d.approval.decided_at).toLocaleString() : ''}; expires{' '}
                    {d.approval?.expires_at ? new Date(d.approval.expires_at).toLocaleString() : ''}.
                  </p>
                  <Button type="button" size="lg" className="w-full" disabled={busy !== null} onClick={() => act('apply', `/deployments/${d.id}/apply`)}>
                    {busy === 'apply' ? 'Queuing…' : 'Apply this plan to AWS'}
                  </Button>
                </>
              ) : (
                <>
                  <label className="flex items-start gap-2 text-sm">
                    <input type="checkbox" className="mt-1" checked={reviewed} onChange={(e) => setReviewed(e.target.checked)} />
                    I reviewed the resources, the cost and the policy checks of this plan.
                  </label>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      disabled={!reviewed || busy !== null}
                      onClick={() => act('approve', `/deployments/${d.id}/approve`, { decision: 'APPROVED', plan_hash: d.plan_hash })}
                    >
                      {busy === 'approve' ? 'Approving…' : 'Approve plan'}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={busy !== null}
                      onClick={() => act('reject', `/deployments/${d.id}/approve`, { decision: 'REJECTED', plan_hash: d.plan_hash, reason: 'Rejected in review' })}
                    >
                      Reject
                    </Button>
                  </div>
                </>
              )}
            </Card>
          ) : null}

          {d.cost_estimate ? (
            <Card title="Cost of this plan">
              <p className="font-display text-3xl font-semibold">
                {formatUsd(d.cost_estimate.monthly_total)}
                <span className="text-sm font-normal text-muted-foreground"> /month</span>
              </p>
              <p className="text-xs text-muted-foreground">
                {d.cost_estimate.source ?? 'AWS Price List'} · pricing as of {d.cost_estimate.pricing_as_of}
                {d.cost_estimate.delta_note ? ` · ${d.cost_estimate.delta_note}` : ''}
              </p>
              <ul className="divide-y text-sm">
                {d.cost_estimate.lines.map((l) => (
                  <li key={l.item} className="flex justify-between gap-3 py-1.5">
                    <span className="min-w-0">
                      <span className="block truncate font-mono text-xs">{l.item}</span>
                      <span className="block text-xs text-muted-foreground">{l.basis}</span>
                    </span>
                    <span className="shrink-0 font-mono">{formatUsd(l.monthly_usd)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {d.policy_results ? (
            <Card title="Policy checks">
              <ul className="space-y-1.5 text-sm">
                {d.policy_results.map((c) => (
                  <li key={c.id} className="flex items-start gap-2">
                    {c.passed ? <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden /> : <X className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />}
                    <span>
                      <span className="sr-only">{c.passed ? 'Passed: ' : 'Failed: '}</span>
                      {c.message}
                    </span>
                  </li>
                ))}
              </ul>
              {failedChecks.length ? <p className="text-xs text-destructive">{failedChecks.length} check(s) failed: this plan cannot be approved.</p> : null}
            </Card>
          ) : null}
        </div>
      </div>

      {d.plan_summary ? (
        <Card title="Plan">
          <p className="text-sm">
            <span className="font-mono text-success">+{d.plan_summary.add}</span> to add ·{' '}
            <span className="font-mono text-warning">~{d.plan_summary.change}</span> to change ·{' '}
            <span className="font-mono text-destructive">-{d.plan_summary.destroy}</span> to destroy
            {d.plan_summary.tofu_version ? <span className="text-muted-foreground"> · OpenTofu {d.plan_summary.tofu_version}</span> : null}
          </p>
          <div className="overflow-x-auto rounded-xl border">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Resources in the OpenTofu plan</caption>
              <thead className="bg-muted/50 text-xs text-muted-foreground">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Action
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Resource
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Type
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {d.plan_summary.resources.map((r) => (
                  <tr key={r.address}>
                    <td className="px-3 py-1.5 font-mono text-xs">{r.action}</td>
                    <td className="px-3 py-1.5 font-mono text-xs">{r.address}</td>
                    <td className="px-3 py-1.5 text-xs text-muted-foreground">{r.type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {d.health ? (
        <Card title="Health check" className={d.health.passed ? 'border-success/50' : 'border-destructive/50'}>
          <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
            <dt className="text-muted-foreground">Result</dt>
            <dd className={d.health.passed ? 'text-success' : 'text-destructive'}>{d.health.passed ? 'Passed' : 'Failed'}</dd>
            <dt className="text-muted-foreground">URL</dt>
            <dd className="break-all font-mono text-xs">{d.health.url}</dd>
            <dt className="text-muted-foreground">Answer</dt>
            <dd className="font-mono text-xs">
              HTTP {d.health.status_code ?? '—'} in {d.health.latency_ms ?? '—'} ms after {d.health.attempts} attempt(s)
            </dd>
            <dt className="text-muted-foreground">ECS service stable</dt>
            <dd>{d.health.ecs_stable ? 'yes' : 'no'}</dd>
          </dl>
          {d.health.body_excerpt ? (
            <pre className="overflow-x-auto rounded-lg bg-black p-3 font-mono text-xs text-zinc-200 ring-1 ring-white/10">{d.health.body_excerpt}</pre>
          ) : null}
        </Card>
      ) : null}

      {DESTROYABLE.has(d.status) && canAdmin ? (
        <Card title="Destroy" className="border-destructive/40">
          <p className="text-sm text-muted-foreground">
            Deletes every resource of this deployment, then checks with the AWS Resource Groups Tagging API that nothing
            tagged with this deployment id remains. Sandbox settings: the database is deleted without a snapshot.
          </p>
          <div className="flex flex-wrap gap-2">
            <Input
              aria-label='Type "destroy" to confirm'
              placeholder='Type "destroy"'
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="max-w-48 font-mono"
            />
            <Button
              type="button"
              variant="destructive"
              disabled={confirm !== 'destroy' || busy !== null}
              onClick={() => act('destroy', `/deployments/${d.id}/destroy`, { confirm: 'destroy' })}
            >
              {busy === 'destroy' ? 'Queuing…' : 'Destroy deployment'}
            </Button>
          </div>
        </Card>
      ) : null}

      {d.destroy_check ? (
        <Card title="After destroy" className={d.destroy_check.clean ? 'border-success/50' : 'border-destructive/50'}>
          <ul className="space-y-1.5 text-sm">
            <li className="flex gap-2">
              {d.destroy_check.clean ? <Check className="mt-0.5 size-4 text-success" aria-hidden /> : <X className="mt-0.5 size-4 text-destructive" aria-hidden />}
              {d.destroy_check.remaining.length} resource(s) tagged cloudpilot:deployment-id={d.id} still exist
            </li>
            <li className="flex gap-2">
              <Check className="mt-0.5 size-4 text-success" aria-hidden />
              {d.destroy_check.remaining_in_state ?? 0} resource(s) left in the OpenTofu state
            </li>
            <li className="text-xs text-muted-foreground">
              {d.destroy_check.indexed_but_gone.length} listed by the tagging index but confirmed deleted ·{' '}
              {d.destroy_check.deleted_task_definitions} ECS task definition revision(s) deleted · checked{' '}
              {d.destroy_check.checked_at ? new Date(d.destroy_check.checked_at).toLocaleString() : ''}
            </li>
          </ul>
          {d.destroy_check.remaining.length ? (
            <ul className="font-mono text-xs text-destructive">
              {d.destroy_check.remaining.map((arn) => (
                <li key={arn}>{arn}</li>
              ))}
            </ul>
          ) : null}
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        {d.resources.length ? (
          <Card title="Resources in AWS">
            <ul className="max-h-72 space-y-1 overflow-y-auto font-mono text-xs" tabIndex={0} aria-label="Resources">
              {d.resources.map((r) => (
                <li key={r.id} className="flex justify-between gap-3">
                  <span className="min-w-0 truncate">{r.resource_name}</span>
                  <span className={r.status === 'DESTROYED' ? 'text-muted-foreground line-through' : ''}>{r.status.toLowerCase()}</span>
                </li>
              ))}
            </ul>
          </Card>
        ) : null}
        {d.sessions.length ? (
          <Card title="CloudTrail sessions">
            <p className="text-xs text-muted-foreground">Every job assumes the deploy role under its own name; search CloudTrail for these.</p>
            <ul className="space-y-1 font-mono text-xs">
              {d.sessions.map((s) => (
                <li key={s.session_name} className="flex justify-between gap-3">
                  <span>{s.session_name}</span>
                  <span className="text-muted-foreground">{s.action}</span>
                </li>
              ))}
            </ul>
          </Card>
        ) : null}
      </div>

      <Card title="Audit trail">
        <p className="text-xs text-muted-foreground">Append-only and hash-chained. Who did what, with which plan hash.</p>
        <ol className="space-y-1.5 text-sm">
          {audit.map((e) => (
            <li key={e.id} className="flex flex-wrap items-baseline gap-x-3">
              <span className="font-mono text-xs text-muted-foreground">{new Date(e.created_at).toLocaleTimeString()}</span>
              <span className="font-medium">{e.action.replaceAll('_', ' ').toLowerCase()}</span>
              {e.plan_hash ? <span className="font-mono text-xs text-muted-foreground">plan {e.plan_hash.slice(0, 12)}</span> : null}
              <span className="font-mono text-[10px] text-muted-foreground">#{e.entry_hash.slice(0, 8)}</span>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  )
}
