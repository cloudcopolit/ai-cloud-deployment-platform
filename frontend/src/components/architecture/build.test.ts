import { describe, expect, it } from 'vitest'

import type { ArchitecturePlan, PlanComponent } from '@/lib/api/schemas'
import { buildSteps, revealAfter } from './build'

const c = (id: string, type: string, depends_on: string[] = []): PlanComponent => ({
  id,
  type,
  depends_on,
  config: {},
  rationale: `why ${id}`
})

/* The prototype plan shape. */
const plan: ArchitecturePlan = {
  schema_version: '1.0',
  source_analysis_id: 'a',
  region: 'us-east-1',
  automated: false,
  components: [
    c('vpc', 'vpc'),
    c('alb', 'alb', ['vpc']),
    c('api', 'ecs_service', ['alb', 'vpc']),
    c('secrets', 'secrets_manager', ['vpc']),
    c('logs', 'cloudwatch', ['api']),
    c('db', 'rds', ['vpc', 'secrets'])
  ],
  assumptions: [{ statement: 'memory under 800 MB', impact: 'MEDIUM', confirmed_by_user: false }],
  security: {
    network_isolation: 'private',
    encryption_at_rest: true,
    encryption_in_transit: true,
    secrets_strategy: 'secrets manager',
    public_endpoints: []
  },
  cost: {
    currency: 'USD',
    monthly_total: 52.5,
    lines: [
      { component_id: 'api', monthly_usd: 18.5, basis: 'x' },
      { component_id: 'alb', monthly_usd: 18, basis: 'x' },
      { component_id: 'db', monthly_usd: 16, basis: 'x' }
    ],
    pricing_as_of: '2026-10-01',
    confidence: 0.9
  },
  risks: []
}

const ctx = { repository: 'acme/shop', services: 1, dataStores: ['postgresql'], recommendation: 'container' }

describe('buildSteps', () => {
  const steps = buildSteps(plan, ctx)

  it('reads the report, frames the VPC, places every non-frame component once, then cost and the gate', () => {
    expect(steps[0]).toMatchObject({ kind: 'read', detail: '1 service · data stores: postgresql · recommended: container' })
    expect(steps[1]).toMatchObject({ kind: 'frame' })
    expect(steps.filter((s) => s.kind === 'node').map((s) => (s.kind === 'node' ? s.id : ''))).toEqual([
      'alb',
      'api',
      'db',
      'secrets',
      'logs'
    ])
    expect(steps.slice(-3).map((s) => s.kind)).toEqual(['cost', 'review', 'gate'])
  })

  it('links only after both ends are on the board, each link once, using the plan rationale', () => {
    const seen = new Set<string>()
    for (const s of steps) {
      if (s.kind === 'node') seen.add(s.id)
      if (s.kind === 'link') {
        expect(s.edge.from === 'users' || seen.has(s.edge.from)).toBe(true)
        expect(seen.has(s.edge.to)).toBe(true)
      }
    }
    const links = steps.filter((s) => s.kind === 'link').map((s) => s.text)
    expect(links).toEqual([
      'Routed Users → Application Load Balancer',
      'Routed Application Load Balancer → ECS on Fargate',
      'Linked Secrets Manager → RDS',
      'Linked ECS on Fargate → CloudWatch'
    ])
    expect(steps.find((s) => s.kind === 'node' && s.id === 'db')?.detail).toBe('why db')
  })

  it('quotes the real cost figures', () => {
    expect(steps.find((s) => s.kind === 'cost')).toMatchObject({
      text: 'Estimated $52.50 per month',
      detail: '3 cost lines; largest: api $18.50 · pricing as of 2026-10-01'
    })
  })
})

describe('revealAfter', () => {
  const steps = buildSteps(plan, ctx)
  it('starts with only the users and grows to everything', () => {
    expect([...revealAfter(steps, 0).nodes]).toEqual(['users'])
    const all = revealAfter(steps, steps.length)
    expect(all.frame).toBe(true)
    expect(all.nodes.size).toBe(6)
    expect(all.links.size).toBe(4)
  })
  it('marks the component just placed as fresh', () => {
    const i = steps.findIndex((s) => s.kind === 'node')
    expect(revealAfter(steps, i + 1).fresh).toBe('alb')
  })
})
