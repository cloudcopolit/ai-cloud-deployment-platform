import { z } from 'zod'

/* Mirrors of backend response schemas. Parsing at the boundary means a backend change shows
 * up as an explicit error state instead of a silently broken screen. */

export const TeamSchema = z.object({
  id: z.string(),
  name: z.string(),
  role: z.enum(['OWNER', 'ADMIN', 'MEMBER']),
  created_at: z.string(),
  member_count: z.number(),
  project_count: z.number(),
  plan_code: z.string()
})
export type Team = z.infer<typeof TeamSchema>

export const ProjectSchema = z.object({
  id: z.string(),
  team_id: z.string(),
  team_name: z.string().nullable().optional(),
  name: z.string(),
  description: z.string().nullable().optional(),
  status: z.enum(['ACTIVE', 'ARCHIVED']),
  created_at: z.string(),
  updated_at: z.string(),
  repository_count: z.number()
})
export type Project = z.infer<typeof ProjectSchema>

export const AccessModeSchema = z.enum(['GITHUB_APP', 'TOKEN', 'ANONYMOUS'])
export type AccessMode = z.infer<typeof AccessModeSchema>

export const RepositorySchema = z.object({
  id: z.string(),
  project_id: z.string(),
  github_repository_id: z.string(),
  owner: z.string(),
  name: z.string(),
  url: z.string(),
  default_branch: z.string(),
  deployment_branch: z.string().nullable(),
  is_private: z.boolean(),
  access_mode: AccessModeSchema,
  branch_count: z.number(),
  branches_truncated: z.boolean(),
  connected_at: z.string(),
  updated_at: z.string(),
  last_synced_at: z.string().nullable()
})
export type Repository = z.infer<typeof RepositorySchema>

export const BranchSchema = z.object({
  id: z.string(),
  repository_id: z.string(),
  name: z.string(),
  is_default: z.boolean(),
  is_deployment_branch: z.boolean()
})
export type Branch = z.infer<typeof BranchSchema>

export const CommitSchema = z.object({
  id: z.string(),
  repository_id: z.string(),
  branch_id: z.string(),
  sha: z.string().regex(/^[0-9a-f]{40}$/),
  message: z.string(),
  author_name: z.string().nullable(),
  committed_at: z.string()
})
export type Commit = z.infer<typeof CommitSchema>

export const GitHubAccessSchema = z.object({
  app_configured: z.boolean(),
  app_installations: z.number().nullable(),
  app_install_url: z.string().nullable(),
  token_configured: z.boolean(),
  rate_limit_remaining: z.number().nullable(),
  rate_limit_limit: z.number().nullable(),
  mode_for_public_repos: AccessModeSchema,
  webhook_enabled: z.boolean()
})
export type GitHubAccess = z.infer<typeof GitHubAccessSchema>

export const ErrorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    correlation_id: z.string().optional(),
    details: z.unknown().optional()
  })
})
