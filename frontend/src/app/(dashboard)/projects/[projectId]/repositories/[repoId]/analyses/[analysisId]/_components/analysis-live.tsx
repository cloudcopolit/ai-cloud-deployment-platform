'use client'

import { useRouter } from 'next/navigation'
import { useCallback, useId, useState } from 'react'

import { ErrorState, Notice } from '@/components/app/states'
import { StatusBadge } from '@/components/app/status-badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { apiFetch } from '@/lib/api/client'
import type { ApiFailure } from '@/lib/api/result'
import { ActivitySchema, AnalysisJobSchema, type Activity, type AnalysisJob } from '@/lib/api/schemas'
import { formatRelative, shortSha } from '@/lib/format'
import { usePoll } from '@/lib/use-poll'
import { ActivityView } from './activity-view'
import { ArchitectHandoff } from './architect-handoff'
import { ReportView } from './report-view'

type Props = {
  initialJob: AnalysisJob
  initialActivity: Activity
  basePath: string
  projectId: string
  architectureHref: string | null
}

const STATUS_SENTENCE: Record<string, string> = {
  QUEUED: 'Waiting for a worker.',
  RUNNING: 'The agents are working.',
  SUCCESS: 'Analysis finished.',
  BLOCKED: 'Analysis finished, but it needs your input before an architecture can be proposed.',
  FAILED: 'Analysis failed.',
  TIMED_OUT: 'Analysis ran out of time.',
  CANCELLED: 'Analysis was cancelled.'
}

function AnswersForm({ job, basePath }: { job: AnalysisJob; basePath: string }) {
  const router = useRouter()
  const formId = useId()
  const questions = job.report?.missing_info ?? []
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [failure, setFailure] = useState<ApiFailure | null>(null)
  const [busy, setBusy] = useState(false)
  if (!questions.length) return null

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    const body = Object.fromEntries(Object.entries(answers).filter(([, v]) => v.trim()))
    const res = await apiFetch(`/analyses/${job.id}/answers`, AnalysisJobSchema, {
      method: 'POST',
      body: { answers: body }
    })
    setBusy(false)
    if (!res.ok) return setFailure(res)
    router.push(`${basePath}/analyses/${res.data.id}`)
  }

  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border border-warning/50 p-4" aria-labelledby={`${formId}-t`}>
      <h3 id={`${formId}-t`} className="font-semibold">
        Answer these questions to continue
      </h3>
      {questions.map((q, i) => (
        <div key={q.key} className="space-y-1.5">
          <Label htmlFor={`${formId}-${i}`}>
            {q.question}
            {q.required ? <span className="text-destructive"> (required)</span> : null}
          </Label>
          <Input
            id={`${formId}-${i}`}
            required={q.required}
            maxLength={255}
            value={answers[q.key] ?? ''}
            onChange={(e) => setAnswers((a) => ({ ...a, [q.key]: e.target.value }))}
          />
        </div>
      ))}
      {failure ? <ErrorState failure={failure} /> : null}
      <Button type="submit" size="lg" disabled={busy}>
        {busy ? 'Queuing…' : 'Re-run the analysis with these answers'}
      </Button>
    </form>
  )
}

export function AnalysisLive({ initialJob, initialActivity, basePath, projectId, architectureHref }: Props) {
  const [job, setJob] = useState(initialJob)
  const [activity, setActivity] = useState(initialActivity)
  const [failure, setFailure] = useState<ApiFailure | null>(null)
  const [cancelling, setCancelling] = useState(false)
  const router = useRouter()

  const tick = useCallback(
    async (signal: AbortSignal) => {
      const [a, j] = await Promise.all([
        apiFetch(`/analyses/${job.id}/activity`, ActivitySchema, { signal }),
        apiFetch(`/analyses/${job.id}`, AnalysisJobSchema, { signal })
      ])
      if (!a.ok || !j.ok) {
        setFailure(!a.ok ? a : (j as Exclude<typeof j, { ok: true }>))
        return { done: false, changed: false }
      }
      setFailure(null)
      const changed = JSON.stringify(a.data.runs) !== JSON.stringify(activity.runs) || j.data.status !== job.status
      setActivity(a.data)
      setJob(j.data)
      // the stepper and step links are server-rendered: re-render them once the job ends
      if (j.data.terminal && !job.terminal) router.refresh()
      return { done: j.data.terminal, changed }
    },
    [job.id, job.status, job.terminal, activity.runs, router]
  )
  usePoll(tick, { enabled: !job.terminal })

  async function cancel() {
    setCancelling(true)
    const res = await apiFetch(`/analyses/${job.id}/cancel`, AnalysisJobSchema, { method: 'POST' })
    setCancelling(false)
    if (res.ok) setJob(res.data)
    else setFailure(res)
  }

  return (
    <div className="space-y-6">
      {failure ? <ErrorState failure={failure} /> : null}

      {job.error_message ? (
        <Notice tone="warning" title={job.error_code ?? 'Error'}>
          {job.error_message}
        </Notice>
      ) : null}

      <section aria-labelledby="activity" className="space-y-3">
        <h2 id="activity" className="text-lg font-semibold">
          Agent activity
        </h2>
        <ActivityView
          runs={activity.runs}
          jobStatus={job.status}
          terminal={job.terminal}
          meta={
            <>
              <StatusBadge status={job.status} compact />
              {/* announced to screen readers as the job progresses */}
              <span role="status" aria-live="polite">
                {STATUS_SENTENCE[job.status]}
              </span>
              <span>
                <span className="font-mono">{shortSha(job.commit_sha)}</span>
                {job.branch_name ? ` on ${job.branch_name}` : ''} · queued {formatRelative(job.created_at)}
                {job.attempts > 1 ? ` · attempt ${job.attempts}` : ''}
              </span>
              {job.cancel_requested && !job.terminal ? <span>cancel requested…</span> : null}
            </>
          }
          actions={
            !job.terminal ? (
              <Button type="button" variant="outline" size="sm" onClick={cancel} disabled={cancelling || job.cancel_requested}>
                {cancelling ? 'Cancelling…' : 'Cancel'}
              </Button>
            ) : null
          }
        />
      </section>

      {job.status === 'BLOCKED' ? <AnswersForm job={job} basePath={basePath} /> : null}

      {job.status === 'SUCCESS' ? (
        <ArchitectHandoff analysisId={job.id} projectId={projectId} existingHref={architectureHref} />
      ) : null}

      {job.report ? (
        <section aria-labelledby="report" className="space-y-3">
          <h2 id="report" className="text-lg font-semibold">
            Report
          </h2>
          <ReportView report={job.report} />
        </section>
      ) : null}
    </div>
  )
}
