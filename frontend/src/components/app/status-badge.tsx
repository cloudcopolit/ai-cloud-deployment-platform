import { Ban, CheckCircle2, CircleDashed, Clock, Loader2, OctagonX, PauseCircle, SkipForward, Timer } from 'lucide-react'

type Status =
  | 'QUEUED'
  | 'RUNNING'
  | 'SUCCESS'
  | 'BLOCKED'
  | 'FAILED'
  | 'TIMED_OUT'
  | 'CANCELLED'
  | 'SKIPPED'
  | string

const STYLE: Record<string, { label: string; className: string; Icon: typeof Clock; spin?: boolean }> = {
  QUEUED: { label: 'Queued', className: 'border-border-strong text-muted-foreground', Icon: Clock },
  RUNNING: { label: 'Running', className: 'border-info/50 text-info', Icon: Loader2, spin: true },
  SUCCESS: { label: 'Succeeded', className: 'border-success/50 text-success', Icon: CheckCircle2 },
  BLOCKED: { label: 'Blocked — needs input', className: 'border-warning/60 text-warning', Icon: PauseCircle },
  FAILED: { label: 'Failed', className: 'border-destructive/50 text-destructive', Icon: OctagonX },
  TIMED_OUT: { label: 'Timed out', className: 'border-destructive/50 text-destructive', Icon: Timer },
  CANCELLED: { label: 'Cancelled', className: 'border-border-strong text-muted-foreground', Icon: Ban },
  SKIPPED: { label: 'Skipped', className: 'border-border-strong text-muted-foreground', Icon: SkipForward }
}

/** Status is always spelled out; color only reinforces it (WCAG 1.4.1). */
export function StatusBadge({ status, compact = false }: { status: Status; compact?: boolean }) {
  const s = STYLE[status] ?? { label: status, className: 'text-muted-foreground', Icon: CircleDashed }
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${s.className}`}
    >
      <s.Icon className={`size-3.5 ${s.spin ? 'animate-spin' : ''}`} aria-hidden />
      {compact && status === 'BLOCKED' ? 'Blocked' : s.label}
    </span>
  )
}
