import { describe, expect, it } from 'vitest'
import {
  CreateProjectSchema,
  ConnectRepositorySchema,
  ProjectSchema,
  TeamSchema
} from './project'

describe('project validations', () => {
  it('validates a correct Project', () => {
    const raw = {
      id: 'd8c47462-8173-455b-801b-520c153835f8',
      team_id: 'e1c47462-8173-455b-801b-520c153835f9',
      team_name: 'Acme Team',
      name: 'Store API',
      description: 'E-commerce API',
      status: 'ACTIVE',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      repository_count: 1,
      deployment_count: 0
    }
    const res = ProjectSchema.safeParse(raw)
    expect(res.success).toBe(true)
  })

  it('rejects invalid project status', () => {
    const raw = {
      id: 'd8c47462-8173-455b-801b-520c153835f8',
      team_id: 'e1c47462-8173-455b-801b-520c153835f9',
      name: 'Store API',
      status: 'DELETED', // Not allowed: only ACTIVE or ARCHIVED
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
    const res = ProjectSchema.safeParse(raw)
    expect(res.success).toBe(false)
  })

  it('validates CreateProjectInput', () => {
    expect(CreateProjectSchema.safeParse({ name: 'Web App' }).success).toBe(true)
    expect(CreateProjectSchema.safeParse({ name: '' }).success).toBe(false)
  })

  it('validates ConnectRepositoryInput URL', () => {
    const valid = {
      github_repository_id: '12345',
      owner: 'acme',
      name: 'repo',
      url: 'https://github.com/acme/repo',
      default_branch: 'main'
    }
    expect(ConnectRepositorySchema.safeParse(valid).success).toBe(true)

    const invalid = { ...valid, url: 'not-a-valid-url' }
    expect(ConnectRepositorySchema.safeParse(invalid).success).toBe(false)
  })

  it('validates TeamSchema', () => {
    const raw = {
      id: 'e1c47462-8173-455b-801b-520c153835f9',
      name: 'DevOps Team',
      role: 'OWNER',
      created_at: new Date().toISOString(),
      member_count: 3,
      project_count: 1,
      plan_code: 'FREE'
    }
    expect(TeamSchema.safeParse(raw).success).toBe(true)
  })
})
