'use client'

import { useState } from 'react'
import { Check, ChevronRight, Loader2, Minus, X } from 'lucide-react'

import { AgentAvatar, AgentPortrait } from '@/components/agents/agent-avatar'
import { StatusBadge } from '@/components/app/status-badge'
import { SpriteIcon } from '@/components/brand/icons'
import { AGENTS, agentFor } from '@/lib/agents'
import { AGENT_PLANS, ANALYSIS_PLAN, stepCopy, summarizeStep } from '@/lib/agent-steps'
import type { AgentRun, AgentTask, JobStatus } from '@/lib/api/schemas'
import { formatDuration } from '@/lib/format'
import { useNow } from '@/lib/use-now'
import { cn } from '@/lib/utils'

/** A row in an agent's timeline: a step that ran or runs, or one it has not reached. */
type Row = { key: string; type: string; task: AgentTask | null }

const OPEN = new Set(['QUEUED', 'RUNNING'])

function rowsFor(run: AgentRun): Row[] {
  const rows: Row[] = [...run.tasks]
    .sort((a, b) => a.step_order - b.step_order)
    .map((t) => ({ key: t.id, type: t.task_type, task: t }))
  const seen = new Set(rows.map((r) => r.type))
  for (const type of AGENT_PLANS[run.agent_type] ?? []) {
    if (!seen.has(type)) rows.push({ key: `planned-${type}`, type, task: null })
  }
  return rows
}

function elapsedMs(startedAt: string | null, completedAt: string | null, now: number): number | null {
  if (!startedAt) return null
  const end = completedAt ? Date.parse(completedAt) : now
  return Math.max(0, end - Date.parse(startedAt))
}

/** The model an agent used, or that it used none. Plain words, no decoration. */
function modelText(run: AgentRun): string {
  const u = run.usage
  if (!u || (!u.calls && !u.model)) return 'No language model used (deterministic)'
  const tokens = u.input_tokens + u.output_tokens
  return [
    u.mocked ? 'MOCKED' : null,
    `${u.provider ?? 'provider ?'} / ${u.model ?? run.model ?? 'model ?'}`,
    `${u.calls} call${u.calls === 1 ? '' : 's'}`,
    `${tokens.toLocaleString('en-US')} tokens`,
    `$${u.cost_usd.toFixed(4)}`
  ]
    .filter(Boolean)
    .join(' · ')
}

function StepIcon({ state }: { state: string }) {
  const base = 'grid size-6 place-items-center rounded-full border bg-background'
  switch (state) {
    case 'RUNNING':
      return (
        <span className={cn(base, 'border-primary/60 text-primary')}>
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
        </span>
      )
    case 'SUCCESS':
      return (
        <span className={cn(base, 'border-success/50 bg-success/10 text-success')}>
          <Check className="size-3.5" aria-hidden />
        </span>
      )
    case 'FAILED':
      return (
        <span className={cn(base, 'border-destructive/60 bg-destructive/10 text-destructive')}>
          <X className="size-3.5" aria-hidden />
        </span>
      )
    case 'SKIPPED':
      return (
        <span className={cn(base, 'text-muted-foreground')}>
          <Minus className="size-3.5" aria-hidden />
        </span>
      )
    default:
      return <span className={cn(base, 'border-dashed border-border-strong')} />
  }
}

const STATE_WORD: Record<string, string> = {
  RUNNING: 'running',
  SUCCESS: 'done',
  FAILED: 'failed',
  SKIPPED: 'skipped',
  QUEUED: 'queued',
  PLANNED: 'next',
  NOT_RUN: 'not run'
}

/** The raw step record, as a terminal-style block (plain text, never HTML). */
function StepDetails({ task }: { task: AgentTask }) {
  return (
    <div className="mt-2 overflow-x-auto rounded-lg bg-black p-3 font-mono text-xs leading-relaxed text-zinc-200 ring-1 ring-white/10">
      <p className="text-zinc-400">
        $ step {task.step_order} · {task.task_type} · {task.status.toLowerCase()} · {formatDuration(task.duration_ms)}
      </p>
      {task.output && Object.keys(task.output).length ? (
        <>
          <p className="mt-2 text-zinc-400">← output</p>
          <pre className="whitespace-pre-wrap break-words">{JSON.stringify(task.output, null, 2)}</pre>
        </>
      ) : null}
      {task.error_message ? (
        <p className="mt-2 text-red-300">
          ✕ {task.error_code}: {task.error_message}
        </p>
      ) : null}
    </div>
  )
}

function StepRow({ row, runOpen, last, now }: { row: Row; runOpen: boolean; last: boolean; now: number }) {
  const t = row.task
  const state = t ? t.status : runOpen ? 'PLANNED' : 'NOT_RUN'
  const [open, setOpen] = useState(state === 'FAILED')
  const copy = stepCopy(row.type)
  const running = state === 'RUNNING'
  const title = running ? copy.running : t ? copy.done : copy.planned
  const summary = t ? summarizeStep(t) : null
  const time = t ? (running ? elapsedMs(t.started_at, null, now) : t.duration_ms) : null
  const expandable = Boolean(t && (t.output || t.error_message))

  const head = (
    <>
      <SpriteIcon name={copy.icon} className={cn('size-4', t ? 'text-muted-foreground' : 'text-muted-foreground/60')} />
      <span
        className={cn(
          'min-w-0 truncate text-sm',
          running && 'shimmer-text font-medium',
          state === 'SUCCESS' && 'text-foreground',
          (state === 'PLANNED' || state === 'NOT_RUN' || state === 'SKIPPED') && 'text-muted-foreground',
          state === 'FAILED' && 'font-medium text-destructive'
        )}
      >
        {title}
        {running ? '…' : ''}
      </span>
      <span className="sr-only">({STATE_WORD[state] ?? state.toLowerCase()})</span>
      <span className="ml-auto shrink-0 pl-3 font-mono text-xs text-muted-foreground tabular-nums">
        {time !== null ? formatDuration(time) : state === 'NOT_RUN' ? 'not run' : ''}
      </span>
      {expandable ? (
        <ChevronRight
          className={cn('size-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-90')}
          aria-hidden
        />
      ) : (
        <span className="size-4 shrink-0" />
      )}
    </>
  )

  return (
    <li className="relative pl-9">
      {!last ? <span aria-hidden className="absolute bottom-[-0.75rem] left-3 top-7 w-px bg-border" /> : null}
      <span className="absolute left-0 top-0.5">
        <StepIcon state={state} />
      </span>
      {expandable ? (
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="-mx-2 flex w-[calc(100%+1rem)] items-center gap-2 rounded-md px-2 py-1 text-left hover:bg-muted/60"
        >
          {head}
        </button>
      ) : (
        <div className="-mx-2 flex items-center gap-2 px-2 py-1">{head}</div>
      )}
      {summary ? <p className="mt-0.5 text-xs text-muted-foreground">{summary}</p> : null}
      {t?.error_message && !open ? (
        <p className="mt-0.5 text-xs text-destructive">
          {t.error_code}: {t.error_message}
        </p>
      ) : null}
      {open && t ? <StepDetails task={t} /> : null}
    </li>
  )
}

function AgentBlock({ run, now }: { run: AgentRun; now: number }) {
  const agent = agentFor(run.agent_type)
  const rows = rowsFor(run)
  const runOpen = OPEN.has(run.status)
  const working = run.status === 'RUNNING'
  const attempt = typeof run.input?.attempt === 'number' && run.input.attempt > 1 ? run.input.attempt : null
  const time = working ? elapsedMs(run.started_at, null, now) : run.duration_ms
  const done = run.tasks.filter((t) => !OPEN.has(t.status)).length

  return (
    <li className={cn('rounded-2xl border bg-card p-4 transition-shadow', working && 'border-primary/50 shadow-md shadow-primary/5')}>
      <div className="flex items-start gap-3">
        {agent ? (
          <AgentAvatar
            agent={agent}
            working={working}
            details={
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 border-t pt-3 text-xs">
                <dt className="text-muted-foreground">This run</dt>
                <dd>
                  <StatusBadge status={run.status} compact />
                </dd>
                <dt className="text-muted-foreground">Model</dt>
                <dd>{modelText(run)}</dd>
                <dt className="text-muted-foreground">Steps</dt>
                <dd className="font-mono">
                  {done} / {rows.length}
                </dd>
              </dl>
            }
          />
        ) : null}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <p className="font-semibold">
              {agent?.name ?? run.agent_type}
              {attempt ? <span className="font-normal text-muted-foreground"> · attempt {attempt}</span> : null}
            </p>
            <span className="ml-auto flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground tabular-nums">{formatDuration(time)}</span>
              <StatusBadge status={run.status} compact />
            </span>
          </div>
          <p className="text-xs text-muted-foreground">{modelText(run)}</p>
        </div>
      </div>
      {run.error_message ? (
        <p className="mt-3 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {run.error_code}: {run.error_message}
        </p>
      ) : null}
      {rows.length ? (
        <ol aria-label={`${agent?.name ?? run.agent_type} steps`} className="mt-4 space-y-3">
          {rows.map((row, i) => (
            <StepRow key={row.key} row={row} runOpen={runOpen} last={i === rows.length - 1} now={now} />
          ))}
        </ol>
      ) : null}
    </li>
  )
}

/** The Orchestrator's start and finish, as quiet event lines around the agents' work. */
function OrchestratorEvent({ run, phase, now }: { run: AgentRun; phase: 'start' | 'end'; now: number }) {
  const limit = typeof run.input?.timeout_s === 'number' ? run.input.timeout_s : null
  return (
    <li className="flex items-center gap-3 px-1 text-sm">
      <AgentPortrait agent={AGENTS.ORCHESTRATOR} size="sm" />
      {phase === 'start' ? (
        <p className="min-w-0 text-muted-foreground">
          <span className="font-medium text-foreground">Orchestrator</span> started the job
          {limit ? ` · time limit ${limit % 60 === 0 ? `${limit / 60} min` : `${limit} s`}` : ''}
        </p>
      ) : (
        <p className="min-w-0 text-muted-foreground">
          <span className="font-medium text-foreground">Orchestrator</span> checked the result
        </p>
      )}
      {phase === 'end' ? (
        <span className="ml-auto flex items-center gap-2">
          <span className="font-mono text-xs text-muted-foreground tabular-nums">
            {formatDuration(elapsedMs(run.started_at, run.completed_at, now))}
          </span>
          <StatusBadge status={run.status} compact />
        </span>
      ) : null}
    </li>
  )
}

/**
 * Live trace of a job, in the style of an agent console: what is running now, every step with
 * its result, and the raw record behind each step.
 */
export function ActivityView({
  runs,
  jobStatus,
  terminal,
  meta,
  actions
}: {
  runs: AgentRun[]
  jobStatus: JobStatus
  terminal: boolean
  /** Job facts (status, commit, queue time) shown under the headline. */
  meta?: React.ReactNode
  actions?: React.ReactNode
}) {
  const now = useNow(!terminal)
  const orchestrator = runs.find((r) => r.agent_type === 'ORCHESTRATOR')
  const agents = runs.filter((r) => r.agent_type !== 'ORCHESTRATOR')

  const allRows = agents.flatMap(rowsFor)
  const total = Math.max(allRows.length, ANALYSIS_PLAN.length)
  const finished = allRows.filter((r) => r.task && !OPEN.has(r.task.status)).length
  const current = agents.find((r) => r.status === 'RUNNING')
  const currentTask = current?.tasks.find((t) => t.status === 'RUNNING')
  const elapsed = orchestrator ? elapsedMs(orchestrator.started_at, orchestrator.completed_at, now) : null
  const pct = terminal ? 100 : Math.round((finished / total) * 100)

  const headline = current
    ? `${agentFor(current.agent_type)?.name ?? current.agent_type}: ${
        currentTask ? stepCopy(currentTask.task_type).running : 'Starting'
      }…`
    : terminal
      ? `Finished · ${finished} of ${total} steps ran`
      : 'Waiting for a worker to pick up the job…'

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border bg-card p-4">
        <div className="flex items-center gap-3">
          {current && agentFor(current.agent_type) ? (
            <AgentPortrait agent={agentFor(current.agent_type)!} size="sm" working />
          ) : (
            <span className="grid size-8 place-items-center rounded-lg bg-muted text-muted-foreground">
              <SpriteIcon name="ui-activity" className="size-4" />
            </span>
          )}
          <p className={cn('min-w-0 flex-1 truncate text-sm font-medium', !terminal && 'shimmer-text')}>{headline}</p>
          <span className="font-mono text-sm tabular-nums text-muted-foreground" title="Elapsed">
            {formatDuration(elapsed)}
          </span>
          {actions}
        </div>
        {meta ? (
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 pl-11 text-xs text-muted-foreground">{meta}</div>
        ) : null}
        <div
          role="progressbar"
          aria-label="Steps finished"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={terminal ? total : finished}
          className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted"
        >
          <div
            className={cn(
              'h-full rounded-full transition-[width] duration-500',
              jobStatus === 'SUCCESS' ? 'bg-success' : terminal ? 'bg-border-strong' : 'bg-brand-gradient'
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <ol aria-label="Agent timeline" className="space-y-3">
        {orchestrator ? <OrchestratorEvent run={orchestrator} phase="start" now={now} /> : null}
        {agents.length === 0 && !terminal ? (
          <li className="rounded-2xl border border-dashed p-4">
            <p className="mb-3 text-sm text-muted-foreground">The Analysis agent will run these steps:</p>
            <ol className="space-y-3">
              {ANALYSIS_PLAN.map((type, i) => (
                <StepRow
                  key={type}
                  row={{ key: type, type, task: null }}
                  runOpen
                  last={i === ANALYSIS_PLAN.length - 1}
                  now={now}
                />
              ))}
            </ol>
          </li>
        ) : null}
        {agents.map((run) => (
          <AgentBlock key={run.id} run={run} now={now} />
        ))}
        {orchestrator && !OPEN.has(orchestrator.status) ? (
          <OrchestratorEvent run={orchestrator} phase="end" now={now} />
        ) : null}
      </ol>
    </div>
  )
}
