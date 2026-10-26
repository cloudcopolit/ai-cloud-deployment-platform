import type { ArchitecturePlan } from '@/lib/api/schemas'
import { formatUsd } from '@/lib/format'
import { describe, edgesOf, type Edge, type Zone } from './catalog'

/** What the board knows about the analysis the plan came from (all from the stored report). */
export type BuildContext = {
  repository: string | null
  services: number | null
  dataStores: string[]
  recommendation: string | null
}

export type BuildStep =
  | { kind: 'read'; text: string; detail: string | null }
  | { kind: 'frame'; text: string; detail: string | null }
  | { kind: 'node'; id: string; iconSrc: string | null; text: string; detail: string }
  | { kind: 'link'; key: string; edge: Edge; text: string; detail: null }
  | { kind: 'cost'; text: string; detail: string }
  | { kind: 'review'; text: string; detail: string | null }
  | { kind: 'gate'; text: string; detail: string }

export const linkKey = (e: Edge) => `${e.from}->${e.to}`

const ZONE_ORDER: Zone[] = ['edge', 'ingress', 'compute', 'data', 'regional']

/**
 * The plan as the ordered decisions it records: read the report, frame the network, place each
 * component with its stated rationale, link what the plan links, then cost, risks and the
 * approval gate. Nothing here is invented: every line comes from the plan or the report.
 */
export function buildSteps(plan: ArchitecturePlan, ctx: BuildContext): BuildStep[] {
  const steps: BuildStep[] = []
  const facts = [
    ctx.services !== null ? `${ctx.services} service${ctx.services === 1 ? '' : 's'}` : null,
    ctx.dataStores.length ? `data stores: ${ctx.dataStores.join(', ')}` : 'no data stores',
    ctx.recommendation ? `recommended: ${ctx.recommendation.replaceAll('_', ' ')}` : null
  ].filter(Boolean)
  steps.push({
    kind: 'read',
    text: ctx.repository ? `Read the analysis report for ${ctx.repository}` : 'Read the analysis report',
    detail: facts.join(' · ')
  })

  const vpc = plan.components.find((c) => c.type === 'vpc')
  if (vpc) steps.push({ kind: 'frame', text: `Drew the network boundary (${vpc.id})`, detail: vpc.rationale })

  const edges = edgesOf(plan.components)
  const placed = new Set<string>(['users'])
  const linked = new Set<string>()
  const ordered = ZONE_ORDER.flatMap((zone) => plan.components.filter((c) => describe(c).zone === zone))
  const names = new Map(plan.components.map((c) => [c.id, describe(c).label]))
  names.set('users', 'Users')

  for (const c of ordered) {
    const info = describe(c)
    steps.push({ kind: 'node', id: c.id, iconSrc: info.iconSrc, text: `Placed ${info.label} (${c.id})`, detail: c.rationale })
    placed.add(c.id)
    for (const e of edges) {
      const key = linkKey(e)
      if (linked.has(key) || !placed.has(e.from) || !placed.has(e.to)) continue
      linked.add(key)
      steps.push({
        kind: 'link',
        key,
        edge: e,
        text: `${e.kind === 'request' ? 'Routed' : 'Linked'} ${names.get(e.from)} → ${names.get(e.to)}`,
        detail: null
      })
    }
  }

  const biggest = [...plan.cost.lines].sort((a, b) => b.monthly_usd - a.monthly_usd)[0]
  steps.push({
    kind: 'cost',
    text: `Estimated ${formatUsd(plan.cost.monthly_total)} per month`,
    detail: `${plan.cost.lines.length} cost line${plan.cost.lines.length === 1 ? '' : 's'}${
      biggest ? `; largest: ${biggest.component_id} ${formatUsd(biggest.monthly_usd)}` : ''
    } · pricing as of ${plan.cost.pricing_as_of}`
  })
  steps.push({
    kind: 'review',
    text: `Recorded ${plan.assumptions.length} assumption${plan.assumptions.length === 1 ? '' : 's'} and ${
      plan.risks.length
    } risk${plan.risks.length === 1 ? '' : 's'}`,
    detail: plan.risks[0]?.message ?? plan.assumptions[0]?.statement ?? null
  })
  steps.push({
    kind: 'gate',
    text: 'Stopped for human approval',
    detail: 'Nothing is created in AWS until an ADMIN or OWNER approves the exact Terraform plan.'
  })
  return steps
}

export type Reveal = { nodes: Set<string>; links: Set<string>; frame: boolean; fresh: string | null }

/** What the board shows after the first `count` steps. */
export function revealAfter(steps: BuildStep[], count: number): Reveal {
  const r: Reveal = { nodes: new Set(['users']), links: new Set(), frame: false, fresh: null }
  for (const step of steps.slice(0, count)) {
    if (step.kind === 'frame') r.frame = true
    if (step.kind === 'node') r.nodes.add(step.id)
    if (step.kind === 'link') r.links.add(step.key)
  }
  const last = steps[count - 1]
  r.fresh = last?.kind === 'node' ? last.id : null
  return r
}

/** How long each kind of step stays "current" while the board builds (ms). */
export const STEP_DELAY: Record<BuildStep['kind'], number> = {
  read: 1100,
  frame: 800,
  node: 750,
  link: 520,
  cost: 1000,
  review: 900,
  gate: 700
}
