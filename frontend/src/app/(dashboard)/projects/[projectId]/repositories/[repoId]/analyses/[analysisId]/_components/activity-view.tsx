import { Bot, Cpu, Workflow } from 'lucide-react'

import { StatusBadge } from '@/components/app/status-badge'
import type { AgentRun, AgentTask } from '@/lib/api/schemas'
import { formatDuration } from '@/lib/format'

const AGENT_COPY: Record<string, { title: string; role: string; Icon: typeof Bot }> = {
  ORCHESTRATOR: {
    title: 'Orchestrator',
    role: 'Decides what runs next, validates every result, enforces time limits.',
    Icon: Workflow
  },
  ANALYSIS: {
    title: 'Analysis agent',
    role: 'Reads the repository as text and detects services, dependencies and risks.',
    Icon: Cpu
  },
  ARCHITECTURE: {
    title: 'Architecture agent',
    role: 'Proposes an AWS architecture with cost, assumptions and risks.',
    Icon: Bot
  }
}

const TASK_LABEL: Record<string, string> = {
  read_repository: 'Read the repository (listed files, read relevant ones)',
  detect_languages_and_frameworks: 'Detect languages, frameworks and dependencies',
  detect_containers_and_config: 'Detect Dockerfiles, Compose, CI and config',
  detect_env_ports_health: 'Find environment variable names, ports, health routes',
  scan_for_secrets: 'Scan for committed secrets (path and kind only)',
  resolve_ambiguity_with_llm: 'Resolve ambiguity with a language model',
  assemble_report: 'Assemble and validate the report'
}

function Summary({ output }: { output: Record<string, unknown> | null }) {
  if (!output) return null
  const entries = Object.entries(output).filter(([, v]) => v !== null && v !== undefined)
  if (!entries.length) return null
  return (
    <dl className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
      {entries.map(([k, v]) => (
        <div key={k} className="flex gap-1">
          <dt>{k.replaceAll('_', ' ')}:</dt>
          {/* values are server summaries rendered as plain text, never HTML */}
          <dd className="font-mono text-foreground">{Array.isArray(v) ? v.join(', ') || '—' : String(v)}</dd>
        </div>
      ))}
    </dl>
  )
}

function TaskRow({ task }: { task: AgentTask }) {
  return (
    <li className="flex items-start gap-3 py-2">
      <span className="mt-0.5 w-6 shrink-0 text-right font-mono text-xs text-muted-foreground">{task.step_order}</span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm">{TASK_LABEL[task.task_type] ?? task.task_type}</span>
          <StatusBadge status={task.status} compact />
          <span className="font-mono text-xs text-muted-foreground">{formatDuration(task.duration_ms)}</span>
        </div>
        <Summary output={task.output} />
        {task.error_message ? (
          <p className="mt-1 text-xs text-destructive">
            {task.error_code}: {task.error_message}
          </p>
        ) : null}
      </div>
    </li>
  )
}

function ModelLine({ run }: { run: AgentRun }) {
  const u = run.usage
  if (!u || (!u.calls && !u.model)) {
    return <span>No language model used (deterministic)</span>
  }
  return (
    <span>
      {u.mocked ? 'MOCKED · ' : ''}
      {u.provider ?? 'provider ?'} / {u.model ?? run.model ?? 'model ?'} · {u.calls} call{u.calls === 1 ? '' : 's'} ·{' '}
      {u.input_tokens + u.output_tokens} tokens · ${u.cost_usd.toFixed(4)}
    </span>
  )
}

export function ActivityView({ runs }: { runs: AgentRun[] }) {
  if (runs.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Waiting for a worker to pick up the job. Jobs run one at a time per worker, oldest first.
      </p>
    )
  }
  return (
    <ol className="space-y-3">
      {runs.map((run) => {
        const copy = AGENT_COPY[run.agent_type] ?? { title: run.agent_type, role: '', Icon: Bot }
        const attempt = typeof run.input?.attempt === 'number' && run.input.attempt > 1 ? ` (attempt ${run.input.attempt})` : ''
        return (
          <li key={run.id} className="rounded-xl border">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b p-3">
              <div className="flex min-w-0 items-start gap-2.5">
                <copy.Icon className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
                <div className="min-w-0">
                  <p className="font-medium">
                    {copy.title}
                    {attempt}
                  </p>
                  <p className="text-xs text-muted-foreground">{copy.role}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    <ModelLine run={run} />
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-muted-foreground">{formatDuration(run.duration_ms)}</span>
                <StatusBadge status={run.status} />
              </div>
            </div>
            {run.error_message ? (
              <p className="border-b px-3 py-2 text-sm text-destructive">
                {run.error_code}: {run.error_message}
              </p>
            ) : null}
            {run.tasks.length ? (
              <ul className="divide-y px-3">
                {run.tasks.map((t) => (
                  <TaskRow key={t.id} task={t} />
                ))}
              </ul>
            ) : null}
          </li>
        )
      })}
    </ol>
  )
}
