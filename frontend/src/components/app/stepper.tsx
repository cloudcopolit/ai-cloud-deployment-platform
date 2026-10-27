import Link from 'next/link'
import { Check, Lock } from 'lucide-react'

export type StepState = 'done' | 'current' | 'todo' | 'locked'

export type Step = {
  id: string
  label: string
  state: StepState
  href?: string
  /** Why a locked step is locked, read by screen readers and shown as a tooltip. */
  reason?: string
}

const DOT: Record<StepState, string> = {
  done: 'border-success bg-success text-background',
  current: 'border-primary bg-primary text-primary-foreground',
  todo: 'border-border-strong text-muted-foreground',
  locked: 'border-dashed border-border-strong text-muted-foreground'
}

/** The journey for one repository: each step is a page, never a modal. */
export function Stepper({ steps }: { steps: Step[] }) {
  return (
    <nav aria-label="Progress">
      <ol className="grid gap-2 sm:grid-cols-[repeat(auto-fit,minmax(9rem,1fr))]">
        {steps.map((step, index) => {
          const body = (
            <span className="flex items-center gap-2.5">
              <span
                className={`grid size-7 shrink-0 place-items-center rounded-full border-2 text-xs font-semibold ${DOT[step.state]}`}
                aria-hidden
              >
                {step.state === 'done' ? (
                  <Check className="size-4" />
                ) : step.state === 'locked' ? (
                  <Lock className="size-3.5" />
                ) : (
                  index + 1
                )}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">{step.label}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {step.state === 'done'
                    ? 'Done'
                    : step.state === 'current'
                      ? 'In progress'
                      : step.state === 'locked'
                        ? (step.reason ?? 'Not available yet')
                        : 'Next'}
                </span>
              </span>
            </span>
          )
          const classes = `block rounded-lg border p-2.5 ${step.state === 'current' ? 'border-primary/60 bg-primary/5' : ''}`
          return (
            <li key={step.id} aria-current={step.state === 'current' ? 'step' : undefined}>
              {step.href && step.state !== 'locked' ? (
                <Link href={step.href} className={`${classes} hover:bg-muted/60`}>
                  {body}
                </Link>
              ) : (
                <span className={classes} title={step.reason}>
                  {body}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
