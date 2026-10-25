import { AlertTriangle, CloudOff, Info, Lock, SearchX, ShieldAlert } from 'lucide-react'
import type { ApiFailure } from '@/lib/api/result'

const FAILURE_COPY: Record<ApiFailure['kind'], { title: string; Icon: typeof Info }> = {
  offline: { title: 'CloudPilot API is unreachable', Icon: CloudOff },
  unauthenticated: { title: 'Your session has ended', Icon: Lock },
  forbidden: { title: 'Your role does not allow this', Icon: ShieldAlert },
  not_found: { title: 'Not found', Icon: SearchX },
  invalid: { title: 'Unexpected response', Icon: AlertTriangle },
  error: { title: 'Something went wrong', Icon: AlertTriangle }
}

/** Renders an API failure honestly: what happened and the safe message from the server. */
export function ErrorState({ failure, action }: { failure: ApiFailure; action?: React.ReactNode }) {
  const { title, Icon } = FAILURE_COPY[failure.kind]
  return (
    <div role="alert" className="rounded-xl border border-destructive/40 bg-destructive/5 p-5">
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden />
        <div className="min-w-0 space-y-1">
          <p className="font-medium">{title}</p>
          <p className="text-sm text-muted-foreground">{failure.message}</p>
          <p className="font-mono text-xs text-muted-foreground">
            {failure.code}
            {failure.status ? ` · HTTP ${failure.status}` : ''}
          </p>
          {action ? <div className="pt-2">{action}</div> : null}
        </div>
      </div>
    </div>
  )
}

export function EmptyState({
  title,
  children,
  action
}: {
  title: string
  children?: React.ReactNode
  action?: React.ReactNode
}) {
  return (
    <div className="rounded-xl border border-dashed p-8 text-center">
      <p className="font-medium">{title}</p>
      {children ? <div className="mx-auto mt-1 max-w-prose text-sm text-muted-foreground">{children}</div> : null}
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  )
}

const NOTICE_STYLES = {
  info: 'border-info/40 bg-info/5 [&_svg]:text-info',
  warning: 'border-warning/50 bg-warning/5 [&_svg]:text-warning',
  success: 'border-success/40 bg-success/5 [&_svg]:text-success'
} as const

export function Notice({
  tone = 'info',
  title,
  children
}: {
  tone?: keyof typeof NOTICE_STYLES
  title: string
  children?: React.ReactNode
}) {
  const Icon = tone === 'warning' ? AlertTriangle : Info
  return (
    <div className={`rounded-xl border p-4 ${NOTICE_STYLES[tone]}`}>
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
        <div className="space-y-1 text-sm">
          <p className="font-medium text-foreground">{title}</p>
          {children ? <div className="text-muted-foreground">{children}</div> : null}
        </div>
      </div>
    </div>
  )
}

/** Labels capability honesty everywhere in the UI (REAL / SIMULATED / MOCKED-ONLY). */
export function CapabilityBadge({ level }: { level: 'REAL' | 'SIMULATED' | 'MOCKED-ONLY' }) {
  const style =
    level === 'REAL'
      ? 'border-success/40 text-success'
      : level === 'SIMULATED'
        ? 'border-warning/50 text-warning'
        : 'border-destructive/40 text-destructive'
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[11px] font-medium ${style}`}
      title={
        level === 'REAL'
          ? 'Runs against the real service'
          : level === 'SIMULATED'
            ? 'Runs against a stand-in (e.g. LocalStack) — not real AWS'
            : 'No real backend configured; shown with a fake'
      }
    >
      {level}
    </span>
  )
}
