import { z } from 'zod'

export const TeamSchema = z.object({
  id: z.string(),
  name: z.string(),
  role: z.string(),
  created_at: z.string(),
  member_count: z.number().default(1),
  project_count: z.number().default(0),
  plan_code: z.string().default('FREE')
})
export type Team = z.infer<typeof TeamSchema>

export const ProjectSchema = z.object({
  id: z.string(),
  team_id: z.string(),
  team_name: z.string().nullable().optional(),
  name: z.string().min(1, 'Project name is required'),
  description: z.string().nullable().optional(),
  status: z.enum(['ACTIVE', 'ARCHIVED']),
  created_at: z.string(),
  updated_at: z.string(),
  repository_count: z.number().default(0),
  deployment_count: z.number().default(0)
})
export type Project = z.infer<typeof ProjectSchema>

export const CreateProjectSchema = z.object({
  name: z.string().min(1, 'Project name is required').max(255),
  description: z.string().max(1000).optional()
})
export type CreateProjectInput = z.infer<typeof CreateProjectSchema>

export const RepositorySchema = z.object({
  id: z.string(),
  project_id: z.string(),
  github_repository_id: z.string(),
  owner: z.string(),
  name: z.string(),
  url: z.string(),
  default_branch: z.string(),
  deployment_branch: z.string().nullable().optional(),
  connected_at: z.string(),
  updated_at: z.string()
})
export type Repository = z.infer<typeof RepositorySchema>

export const ConnectRepositorySchema = z.object({
  github_repository_id: z.string().min(1),
  owner: z.string().min(1),
  name: z.string().min(1),
  url: z.string().url(),
  default_branch: z.string().default('main')
})
export type ConnectRepositoryInput = z.infer<typeof ConnectRepositorySchema>

export const AvailableRepositorySchema = z.object({
  id: z.string(),
  name: z.string(),
  full_name: z.string(),
  description: z.string().nullable().optional(),
  default_branch: z.string().default('main'),
  url: z.string(),
  language: z.string().nullable().optional(),
  is_template: z.boolean().default(false)
})
export type AvailableRepository = z.infer<typeof AvailableRepositorySchema>
