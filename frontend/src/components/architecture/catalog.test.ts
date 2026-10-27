import { readdirSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

import type { PlanComponent } from '@/lib/api/schemas'
import { AWS_ICONS } from '@/lib/aws-icons/manifest'
import { describe as describeNode, edgesOf } from './catalog'

const c = (id: string, type: string, depends_on: string[] = []): PlanComponent => ({
  id,
  type,
  depends_on,
  config: {},
  rationale: 'because'
})

describe('official AWS icon manifest', () => {
  it('points at files that exist with the exact (case-sensitive) name', () => {
    const files = new Set(readdirSync(join(process.cwd(), 'public', 'aws-icons')))
    for (const icon of Object.values(AWS_ICONS)) {
      expect(files.has(icon.src.replace('/aws-icons/', ''))).toBe(true)
    }
  })
})

describe('diagram catalog', () => {
  it('uses the official icon for known types and a neutral box for unknown ones', () => {
    expect(describeNode(c('db', 'rds')).iconSrc).toBe('/aws-icons/rds.svg')
    const unknown = describeNode(c('kafka-connect', 'other'))
    expect(unknown.iconSrc).toBeNull()
    expect(unknown.label).toBe('kafka-connect')
  })

  it('draws only links the plan states, with users entering at the front door', () => {
    // the prototype plan shape: everything depends on the VPC frame
    const plan = [
      c('vpc', 'vpc'),
      c('alb', 'alb', ['vpc']),
      c('api', 'ecs_service', ['alb', 'vpc']),
      c('logs', 'cloudwatch', ['api']),
      c('db', 'rds', ['vpc', 'secrets']),
      c('secrets', 'secrets_manager', ['vpc'])
    ]
    expect(edgesOf(plan)).toEqual([
      { from: 'alb', to: 'api', kind: 'request' },
      { from: 'api', to: 'logs', kind: 'dependency' },
      { from: 'secrets', to: 'db', kind: 'dependency' },
      { from: 'users', to: 'alb', kind: 'request' }
    ])
  })

  it('does not send users to a load balancer that sits behind CloudFront', () => {
    const edges = edgesOf([c('cdn', 'cloudfront'), c('alb', 'alb', ['cdn'])])
    expect(edges.filter((e) => e.from === 'users')).toEqual([{ from: 'users', to: 'cdn', kind: 'request' }])
  })
})

/* Three different plans must render; covered in e2e. Here: each zone a plan can use is known. */
describe('zones', () => {
  it.each([
    ['ecs_service', 'compute'],
    ['alb', 'ingress'],
    ['cloudfront', 'edge'],
    ['s3', 'regional'],
    ['msk', 'data']
  ])('%s → %s', (type, zone) => {
    expect(describeNode(c('x', type)).zone).toBe(zone)
  })
})
