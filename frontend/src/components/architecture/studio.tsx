'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, RotateCcw } from 'lucide-react'

import { AgentPortrait } from '@/components/agents/agent-avatar'
import { SpriteIcon } from '@/components/brand/icons'
import { Button } from '@/components/ui/button'
import { AGENTS } from '@/lib/agents'
import type { ArchitecturePlan } from '@/lib/api/schemas'
import { cn } from '@/lib/utils'
import { buildSteps, revealAfter, STEP_DELAY, type BuildContext, type BuildStep } from './build'
import { ArchitectureDiagram } from './diagram'

const reducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

function StepGlyph({ step }: { step: BuildStep }) {
  const box = 'grid size-6 shrink-0 place-items-center rounded-md border bg-background'
  if (step.kind === 'node') {
    return (
      <span className={cn(box, 'bg-icon-surface')}>
        {step.iconSrc ? (
          // official AWS icon, unmodified
          // eslint-disable-next-line @next/next/no-img-element
          <img src={step.iconSrc} alt="" className="size-4" />
        ) : (
          <SpriteIcon name="ui-box" className="size-3.5 text-slate-500" />
        )}
      </span>
    )
  }
  const icon = {
    read: 'ui-file-code',
    frame: 'ui-layers',
    link: 'ui-link',
    cost: 'ui-dollar',
    review: 'ui-alert-triangle',
    gate: 'ui-shield-check'
  }[step.kind] as `ui-${string}`
  return (
    <span className={cn(box, step.kind === 'gate' ? 'text-success' : 'text-muted-foreground')}>
      <SpriteIcon name={icon} className="size-3.5" />
    </span>
  )
}

/**
 * The Architect's board: the diagram builds up step by step (components placed, links drawn)
 * while a reasoning panel narrates each decision the plan records. It replays the stored plan;
 * it does not invent reasoning the agent did not record.
 */
export function ArchitectureStudio({
  plan,
  context,
  autoplay
}: {
  plan: ArchitecturePlan
  context: BuildContext
  autoplay: boolean
}) {
  const steps = useMemo(() => buildSteps(plan, context), [plan, context])
  const [count, setCount] = useState(() => (autoplay ? 0 : steps.length))
  const [open, setOpen] = useState(autoplay)
  const listRef = useRef<HTMLOListElement>(null)
  const building = count < steps.length

  useEffect(() => {
    if (!building) return
    // with reduced motion the finished board appears at once
    const id = reducedMotion()
      ? setTimeout(() => setCount(steps.length), 0)
      : setTimeout(() => setCount((n) => n + 1), count === 0 ? 400 : STEP_DELAY[steps[count - 1].kind])
    return () => clearTimeout(id)
  }, [building, count, steps])

  // keep the newest thought in view, like a streaming transcript
  useEffect(() => {
    const list = listRef.current
    if (list && building) list.scrollTo({ top: list.scrollHeight, behavior: 'smooth' })
  }, [count, building])

  const reveal = building ? revealAfter(steps, count) : null
  const shown = steps.slice(0, count)
  const current = shown.at(-1)

  function replay() {
    setOpen(true)
    setCount(0)
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <ArchitectureDiagram plan={plan} reveal={reveal} />

      <aside
        aria-label="Architect agent reasoning"
        className="flex h-fit max-h-[44rem] flex-col overflow-hidden rounded-2xl border bg-card"
      >
        <div className="flex items-center gap-3 border-b p-3">
          <AgentPortrait agent={AGENTS.ARCHITECTURE} size="sm" working={building} />
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="flex min-w-0 flex-1 items-center gap-1.5 text-left text-sm font-medium"
          >
            <span className={cn('truncate', building && 'shimmer-text')}>
              {building ? 'Thinking…' : `Reasoning · ${steps.length} steps`}
            </span>
            <ChevronDown
              className={cn('size-4 shrink-0 text-muted-foreground transition-transform', !open && '-rotate-90')}
              aria-hidden
            />
          </button>
          <Button type="button" variant="ghost" size="sm" onClick={replay} disabled={building}>
            <RotateCcw className="size-3.5" aria-hidden />
            Replay
          </Button>
        </div>

        {/* one polite announcement per step for screen readers */}
        <p className="sr-only" role="status" aria-live="polite">
          {building && current ? current.text : ''}
        </p>

        {open ? (
          <ol
            ref={listRef}
            tabIndex={0}
            aria-label="Reasoning steps"
            className="flex-1 space-y-3 overflow-y-auto p-3"
          >
            {(building ? shown : steps).map((step, i, all) => {
              const live = building && i === all.length - 1
              return (
                <li key={i} className="flex gap-2.5 animate-in fade-in-0 slide-in-from-bottom-1 duration-300">
                  <StepGlyph step={step} />
                  <div className="min-w-0 space-y-0.5">
                    <p className={cn('text-sm leading-snug', live ? 'shimmer-text font-medium' : 'text-foreground')}>
                      {step.text}
                    </p>
                    {step.detail ? (
                      <p className="line-clamp-3 text-xs leading-relaxed text-muted-foreground">{step.detail}</p>
                    ) : null}
                  </div>
                </li>
              )
            })}
            {building && count === 0 ? (
              <li className="shimmer-text text-sm font-medium">Opening the analysis report…</li>
            ) : null}
          </ol>
        ) : null}

        <p className="border-t px-3 py-2 text-[11px] leading-relaxed text-muted-foreground">
          A replay of the stored plan, step by step. The prototype architect writes the plan in one go; live reasoning
          from a language model arrives with the real Architect agent (WORKLOG S4).
        </p>
      </aside>
    </div>
  )
}
