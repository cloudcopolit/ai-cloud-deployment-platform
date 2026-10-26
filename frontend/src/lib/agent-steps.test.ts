import { describe, expect, it } from 'vitest'
import { ANALYSIS_PLAN, stepCopy, summarizeStep } from './agent-steps'

const step = (task_type: string, output: Record<string, unknown> | null, status = 'SUCCESS' as const) => ({
  task_type,
  status,
  output
})

describe('summarizeStep (outputs recorded for Delivery-Plus0/delivery-plus@dev)', () => {
  it.each([
    ['read_repository', { truncated: false, files_read: 257, unreadable: 0, files_listed: 678 }, 'Listed 678 files, read 257'],
    [
      'detect_languages_and_frameworks',
      { frameworks: ['NestJS'], dependencies: 269, service_candidates: 12 },
      'NestJS · 269 dependencies · 12 service candidates'
    ],
    [
      'detect_containers_and_config',
      { data_stores: ['kafka', 'postgresql', 'redis'], dockerfiles: 13, config_files: 14 },
      '13 Dockerfiles · 14 config files · data stores: kafka, postgresql, redis'
    ],
    [
      'detect_env_ports_health',
      { ports_found: 12, env_var_names: 101, health_routes: 1 },
      '12 ports · 101 env variable names · 1 health route'
    ],
    ['scan_for_secrets', { possible_secrets: 0 }, 'No committed secrets found'],
    ['scan_for_secrets', { possible_secrets: 2 }, '2 possible secrets (file and kind only)'],
    [
      'assemble_report',
      { blockers: 0, services: 12, warnings: 2, missing_info: 0, recommendation: 'container' },
      '12 services · 0 blockers · 2 warnings · recommends container'
    ]
  ])('%s', (type, output, expected) => {
    expect(summarizeStep(step(type, output))).toBe(expected)
  })

  it('explains a skipped step with its reason', () => {
    expect(
      summarizeStep({ task_type: 'resolve_ambiguity_with_llm', status: 'SKIPPED', output: { reason: 'no LLM provider is configured' } })
    ).toBe('Skipped: no LLM provider is configured')
  })

  it('never hides an unknown output', () => {
    expect(summarizeStep(step('new_step', { files: 3, nested: { a: 1 } }))).toBe('files: 3')
    expect(summarizeStep(step('new_step', null))).toBeNull()
  })
})

describe('stepCopy', () => {
  it('has present-progressive copy for every planned analysis step', () => {
    for (const type of ANALYSIS_PLAN) expect(stepCopy(type).running).toMatch(/ing\b/)
  })
  it('falls back to a readable label', () => {
    expect(stepCopy('fetch_tree').done).toBe('Fetch tree')
  })
})
