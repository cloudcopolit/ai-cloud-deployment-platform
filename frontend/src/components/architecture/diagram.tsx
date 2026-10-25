'use client'

import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react'

import { AgentPortrait } from '@/components/agents/agent-avatar'
import { SpriteIcon } from '@/components/brand/icons'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { AGENTS } from '@/lib/agents'
import type { ArchitecturePlan, PlanComponent } from '@/lib/api/schemas'
import { AWS_ICONS } from '@/lib/aws-icons/manifest'
import { formatUsd } from '@/lib/format'
import { cn } from '@/lib/utils'
import { describe, edgesOf, type Edge, type Zone } from './catalog'

type Line = Edge & { d: string }

/** Cubic link between two node boxes, leaving and entering on the facing sides. */
function linkPath(a: DOMRect, b: DOMRect, origin: DOMRect): string {
  const ax = a.left + a.width / 2 - origin.left
  const ay = a.top + a.height / 2 - origin.top
  const bx = b.left + b.width / 2 - origin.left
  const by = b.top + b.height / 2 - origin.top
  if (Math.abs(bx - ax) >= Math.abs(by - ay)) {
    const dir = Math.sign(bx - ax) || 1
    const x1 = ax + (dir * a.width) / 2
    const x2 = bx - (dir * b.width) / 2
    const mid = (x1 + x2) / 2
    return `M ${x1} ${ay} C ${mid} ${ay}, ${mid} ${by}, ${x2} ${by}`
  }
  const dir = Math.sign(by - ay) || 1
  const y1 = ay + (dir * a.height) / 2
  const y2 = by - (dir * b.height) / 2
  const mid = (y1 + y2) / 2
  return `M ${ax} ${y1} C ${ax} ${mid}, ${bx} ${mid}, ${bx} ${y2}`
}

function NodeTile({ src, size = 'md' }: { src: string | null; size?: 'md' | 'sm' }) {
  const box = size === 'md' ? 'size-14' : 'size-10'
  return (
    <span
      className={cn(
        'grid shrink-0 place-items-center rounded-xl border bg-icon-surface shadow-sm',
        box
      )}
    >
      {src ? (
        // official AWS icon, unmodified, on a light tile in both themes (icon terms)
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" className={size === 'md' ? 'size-10' : 'size-7'} />
      ) : (
        <SpriteIcon name="ui-box" className="size-6 text-slate-500" />
      )}
    </span>
  )
}

function ComponentNode({
  component,
  plan,
  active,
  onActive
}: {
  component: PlanComponent
  plan: ArchitecturePlan
  active: string | null
  onActive: (id: string | null) => void
}) {
  const info = describe(component)
  const cost = plan.cost.lines.find((l) => l.component_id === component.id)
  const dimmed = active !== null && active !== component.id
  const config = Object.entries(component.config).filter(([, v]) => v !== null && v !== '')
  return (
    <Popover onOpenChange={(open) => onActive(open ? component.id : null)}>
      <PopoverTrigger
        data-node={component.id}
        onMouseEnter={() => onActive(component.id)}
        onMouseLeave={() => onActive(null)}
        onFocus={() => onActive(component.id)}
        onBlur={() => onActive(null)}
        className={cn(
          'flex w-36 flex-col items-center gap-1.5 rounded-xl p-2 text-center transition',
          'hover:bg-background/80 focus-visible:bg-background/80',
          dimmed && 'opacity-50'
        )}
      >
        <NodeTile src={info.iconSrc} />
        <span className="text-xs font-medium leading-tight">{info.label}</span>
        <span className="max-w-full truncate font-mono text-[10px] text-muted-foreground">{component.id}</span>
      </PopoverTrigger>
      <PopoverContent className="w-96 space-y-3 text-sm">
        <div className="flex items-start gap-3">
          <NodeTile src={info.iconSrc} size="sm" />
          <div className="min-w-0">
            <p className="font-semibold">{info.service}</p>
            <p className="font-mono text-xs text-muted-foreground">
              {component.id}
              {component.serves_service ? ` · serves ${component.serves_service}` : ''}
            </p>
          </div>
        </div>
        <div>
          <p className="text-xs font-medium text-muted-foreground">Why the Architect chose it</p>
          {/* plan text is rendered as plain text, never HTML */}
          <p>{component.rationale}</p>
        </div>
        {config.length ? (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 rounded-lg bg-muted p-2 text-xs">
            {config.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted-foreground">{k.replaceAll('_', ' ')}</dt>
                <dd className="font-mono">{Array.isArray(v) ? v.join(', ') : String(v)}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        {component.depends_on.length ? (
          <p className="text-xs text-muted-foreground">Depends on: {component.depends_on.join(', ')}</p>
        ) : null}
        {cost ? (
          <p className="flex justify-between gap-3 border-t pt-2 text-xs">
            <span className="text-muted-foreground">{cost.basis}</span>
            <span className="shrink-0 font-mono">{formatUsd(cost.monthly_usd)}/mo</span>
          </p>
        ) : null}
      </PopoverContent>
    </Popover>
  )
}

function Frame({
  icon,
  title,
  subtitle,
  className,
  children
}: {
  icon: string
  title: string
  subtitle?: string
  className?: string
  children: React.ReactNode
}) {
  return (
    <div className={cn('relative rounded-2xl border-2 p-4 pt-10', className)}>
      <div className="absolute left-0 top-0 flex items-center gap-2">
        {/* official group icon; it is the frame's corner tab */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={icon} alt="" className="size-8 rounded-tl-xl" />
        <span className="text-xs font-semibold">{title}</span>
        {subtitle ? <span className="font-mono text-[11px] text-muted-foreground">{subtitle}</span> : null}
      </div>
      {children}
    </div>
  )
}

/**
 * The plan as an AWS diagram: official icons, VPC and region frames, and the links the plan
 * states. Every node opens its rationale. The table on the page is the accessible alternative.
 */
export function ArchitectureDiagram({ plan }: { plan: ArchitecturePlan }) {
  const canvas = useRef<HTMLDivElement>(null)
  const [lines, setLines] = useState<Line[]>([])
  const [active, setActive] = useState<string | null>(null)
  const edges = useMemo(() => edgesOf(plan.components), [plan.components])
  const hasVpc = plan.components.some((c) => c.type === 'vpc')

  const zones = useMemo(() => {
    const out: Record<Zone, PlanComponent[]> = { edge: [], ingress: [], compute: [], data: [], regional: [], frame: [] }
    for (const c of plan.components) out[describe(c).zone].push(c)
    return out
  }, [plan.components])

  const measure = useCallback(() => {
    const root = canvas.current
    if (!root) return
    const origin = root.getBoundingClientRect()
    const box = (id: string) => root.querySelector(`[data-node="${CSS.escape(id)}"]`)?.getBoundingClientRect()
    const next: Line[] = []
    for (const e of edges) {
      const a = box(e.from)
      const b = box(e.to)
      if (a && b) next.push({ ...e, d: linkPath(a, b, origin) })
    }
    setLines(next)
  }, [edges])

  useLayoutEffect(() => {
    measure()
    const root = canvas.current
    if (!root) return
    const observer = new ResizeObserver(measure)
    observer.observe(root)
    return () => observer.disconnect()
  }, [measure])

  const node = (c: PlanComponent) => (
    <ComponentNode key={c.id} component={c} plan={plan} active={active} onActive={setActive} />
  )
  const column = (title: string, items: PlanComponent[]) =>
    items.length ? (
      <div className="flex flex-col items-center gap-2">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
        {items.map(node)}
      </div>
    ) : null

  const inner = (
    <div className="flex flex-wrap items-center justify-around gap-6">
      {column('Load balancing', zones.ingress)}
      {column('Compute', zones.compute)}
      {column('Data', zones.data)}
    </div>
  )

  return (
    <figure aria-label="Architecture diagram" className="space-y-3">
      <div className="overflow-x-auto rounded-2xl border bg-muted/30">
        <div ref={canvas} className="bg-grid relative min-w-[760px] p-6">
          <svg aria-hidden className="pointer-events-none absolute inset-0 size-full overflow-visible">
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0 0 10 5 0 10z" className="fill-primary" />
              </marker>
              <marker id="arrow-muted" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0 0 10 5 0 10z" className="fill-border-strong" />
              </marker>
            </defs>
            {lines.map((l) => {
              const lit = active === null || active === l.from || active === l.to
              return (
                <path
                  key={`${l.from}-${l.to}`}
                  d={l.d}
                  fill="none"
                  strokeWidth={lit && active !== null ? 2.5 : 1.75}
                  markerEnd={l.kind === 'request' ? 'url(#arrow)' : 'url(#arrow-muted)'}
                  className={cn(
                    'transition-opacity',
                    l.kind === 'request' ? 'link-flow stroke-primary' : 'stroke-border-strong [stroke-dasharray:4_4]',
                    !lit && 'opacity-15'
                  )}
                />
              )
            })}
          </svg>

          <div className="relative flex items-center gap-8">
            <div className="flex flex-col items-center gap-1.5" data-node="users">
              <NodeTile src={AWS_ICONS.users.src} />
              <span className="text-xs font-medium">Users</span>
              <span className="text-[10px] text-muted-foreground">Internet</span>
            </div>

            <Frame
              icon={AWS_ICONS.group_aws_cloud.src}
              title="AWS Cloud"
              subtitle={plan.region}
              className="flex-1 space-y-5 border-border-strong/60 bg-background/60"
            >
              {zones.edge.length ? (
                <div className="flex flex-wrap justify-center gap-4">{zones.edge.map(node)}</div>
              ) : null}
              {hasVpc ? (
                <Frame icon={AWS_ICONS.group_vpc.src} title="VPC" className="border-[#8c4fff]/60">
                  {inner}
                </Frame>
              ) : (
                inner
              )}
              {zones.regional.length ? (
                <div className="space-y-2 border-t border-dashed pt-4">
                  <p className="text-center text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                    Regional services
                  </p>
                  <div className="flex flex-wrap justify-center gap-4">{zones.regional.map(node)}</div>
                </div>
              ) : null}
            </Frame>
          </div>

          <div className="absolute bottom-3 right-3 flex items-center gap-2 rounded-full border bg-background/90 py-1 pl-1 pr-3 text-xs shadow-sm">
            <AgentPortrait agent={AGENTS.ARCHITECTURE} size="sm" />
            Drawn from the Architect agent&apos;s plan
          </div>
        </div>
      </div>
      <figcaption className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <svg aria-hidden width="28" height="6">
            <path d="M0 3h28" className="stroke-primary" strokeWidth="2" strokeDasharray="6 6" />
          </svg>
          Request path
        </span>
        <span className="flex items-center gap-1.5">
          <svg aria-hidden width="28" height="6">
            <path d="M0 3h28" className="stroke-border-strong" strokeWidth="2" strokeDasharray="4 4" />
          </svg>
          A → B: B depends on A
        </span>
        <span>Select a component for its rationale. Official AWS Architecture Icons.</span>
      </figcaption>
    </figure>
  )
}
