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
  app_installations_usable: z.number().nullable().optional(),
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

/* ───────────── analysis jobs (05 §3.4) ───────────── */

export const JobStatusSchema = z.enum(['QUEUED', 'RUNNING', 'SUCCESS', 'BLOCKED', 'FAILED', 'TIMED_OUT', 'CANCELLED'])
export type JobStatus = z.infer<typeof JobStatusSchema>

const EvidenceSchema = z.object({
  file_path: z.string(),
  line_start: z.number().nullable().optional(),
  detector: z.string()
})
const FindingSchema = z.object({
  code: z.string(),
  severity: z.enum(['BLOCKER', 'WARNING', 'INFO']),
  message: z.string(),
  evidence: z.array(EvidenceSchema).default([]),
  suggested_action: z.string().nullable().optional()
})
export type Finding = z.infer<typeof FindingSchema>

const ServiceSchema = z.object({
  name: z.string(),
  service_type: z.string(),
  language: z.string().nullable(),
  framework: z.string().nullable(),
  path: z.string(),
  port: z.number().nullable(),
  has_dockerfile: z.boolean(),
  health_endpoint: z.string().nullable(),
  confidence: z.number(),
  metadata: z.record(z.string(), z.unknown()).default({}),
  evidence: z.array(EvidenceSchema).default([])
})
export type DetectedService = z.infer<typeof ServiceSchema>

export const ReportSchema = z.object({
  schema_version: z.string(),
  summary: z.string(),
  languages: z.array(z.object({ name: z.string(), share_percent: z.number().nullable().optional() })).default([]),
  frameworks: z.array(z.object({ name: z.string(), version: z.string().nullable().optional(), kind: z.string() })).default([]),
  services: z.array(ServiceSchema).default([]),
  dependencies: z.array(z.object({ ecosystem: z.string(), name: z.string(), dev_only: z.boolean() })).default([]),
  config_files: z.array(z.object({ path: z.string(), kind: z.string() })).default([]),
  data_stores: z.array(
    z.object({ engine: z.string(), inferred_from: z.string(), confidence: z.number(), evidence: z.array(EvidenceSchema).default([]) })
  ).default([]),
  env_vars: z.array(z.object({ name: z.string(), required: z.boolean(), referenced_in: z.string().nullable().optional() })).default([]),
  blockers: z.array(FindingSchema).default([]),
  warnings: z.array(FindingSchema).default([]),
  missing_info: z.array(z.object({ key: z.string(), question: z.string(), required: z.boolean() })).default([]),
  unsupported: z.array(z.object({ name: z.string(), reason: z.string() })).default([]),
  recommendation: z
    .object({
      method: z.enum(['container', 'static_site', 'serverless', 'unsupported']),
      reasoning: z.string(),
      services: z.array(z.string()).default([]),
      automated_by_cloudpilot: z.boolean(),
      confidence: z.number()
    })
    .nullable()
    .optional(),
  overall_confidence: z.number(),
  meta: z.object({
    analyzer_version: z.string(),
    files_scanned: z.number(),
    files_skipped: z.number(),
    truncated: z.boolean(),
    duration_ms: z.number(),
    model: z.string().nullable().optional()
  })
})
export type Report = z.infer<typeof ReportSchema>

export const AnalysisJobSchema = z.object({
  id: z.string(),
  repository_id: z.string(),
  project_id: z.string(),
  commit_sha: z.string(),
  branch_name: z.string().nullable(),
  status: JobStatusSchema,
  terminal: z.boolean(),
  created_at: z.string(),
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  duration_ms: z.number().nullable(),
  attempts: z.number(),
  cancel_requested: z.boolean(),
  parent_analysis_id: z.string().nullable(),
  user_answers: z.record(z.string(), z.string()).default({}),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
  warnings: z.array(z.object({ code: z.string(), message: z.string() }).passthrough()).default([]),
  services_count: z.number(),
  report: ReportSchema.nullable()
})
export type AnalysisJob = z.infer<typeof AnalysisJobSchema>

const TaskSchema = z.object({
  id: z.string(),
  task_type: z.string(),
  status: z.enum(['QUEUED', 'RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED']),
  step_order: z.number(),
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  duration_ms: z.number().nullable(),
  output: z.record(z.string(), z.unknown()).nullable(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable()
})
export type AgentTask = z.infer<typeof TaskSchema>

const UsageSchema = z.object({
  provider: z.string().nullable().optional(),
  model: z.string().nullable().optional(),
  calls: z.number().default(0),
  input_tokens: z.number().default(0),
  output_tokens: z.number().default(0),
  cost_usd: z.number().default(0),
  latency_ms: z.number().default(0),
  mocked: z.boolean().default(false)
})

const RunSchema = z.object({
  id: z.string(),
  agent_type: z.string(),
  status: JobStatusSchema,
  model: z.string().nullable(),
  usage: UsageSchema.nullable(),
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  duration_ms: z.number().nullable(),
  input: z.record(z.string(), z.unknown()).nullable(),
  output: z.record(z.string(), z.unknown()).nullable(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
  tasks: z.array(TaskSchema)
})
export type AgentRun = z.infer<typeof RunSchema>

export const ActivitySchema = z.object({
  analysis_id: z.string(),
  status: JobStatusSchema,
  terminal: z.boolean(),
  attempts: z.number(),
  cancel_requested: z.boolean(),
  heartbeat_at: z.string().nullable(),
  runs: z.array(RunSchema)
})
export type Activity = z.infer<typeof ActivitySchema>

/* ── Architecture (ArchitecturePlan contract, ai/src/cloudpilot_ai/contracts.py) ── */

export const PlanComponentSchema = z.object({
  id: z.string(),
  type: z.string(),
  serves_service: z.string().nullable().optional(),
  config: z.record(z.string(), z.unknown()).default({}),
  depends_on: z.array(z.string()).default([]),
  rationale: z.string()
})
export type PlanComponent = z.infer<typeof PlanComponentSchema>

const CostLineSchema = z.object({ component_id: z.string(), monthly_usd: z.number(), basis: z.string() })

export const ArchitecturePlanSchema = z.object({
  schema_version: z.string(),
  source_analysis_id: z.string(),
  region: z.string(),
  components: z.array(PlanComponentSchema),
  assumptions: z
    .array(z.object({ statement: z.string(), impact: z.string(), confirmed_by_user: z.boolean().default(false) }))
    .default([]),
  security: z.object({
    network_isolation: z.string(),
    encryption_at_rest: z.boolean(),
    encryption_in_transit: z.boolean(),
    secrets_strategy: z.string(),
    least_privilege_notes: z.string().nullable().optional(),
    public_endpoints: z.array(z.string()).default([])
  }),
  cost: z.object({
    currency: z.string(),
    monthly_total: z.number(),
    lines: z.array(CostLineSchema).default([]),
    pricing_as_of: z.string(),
    confidence: z.number()
  }),
  risks: z.array(FindingSchema).default([])
})
export type ArchitecturePlan = z.infer<typeof ArchitecturePlanSchema>

export const ArchitectureVersionSchema = z.object({
  id: z.string(),
  architecture_id: z.string(),
  version_number: z.number(),
  source_analysis_id: z.string().nullable(),
  status: z.string(),
  architecture_data: z.record(z.string(), z.unknown()),
  created_by: z.string().nullable(),
  created_at: z.string(),
  monthly_cost: z.number()
})
export type ArchitectureVersion = z.infer<typeof ArchitectureVersionSchema>

export const ArchitectureSchema = z.object({
  id: z.string(),
  project_id: z.string(),
  name: z.string(),
  status: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  versions_count: z.number(),
  latest_version: ArchitectureVersionSchema.nullable()
})
export type Architecture = z.infer<typeof ArchitectureSchema>

export const LlmProviderSchema = z.object({
  provider: z.string(),
  mode: z.enum(['REAL', 'MOCKED-ONLY']),
  configured: z.boolean(),
  reachable: z.boolean().nullable(),
  models_listed: z.number().nullable(),
  chosen_model: z.string().nullable(),
  latency_ms: z.number().nullable(),
  error: z.string().nullable()
})
export type LlmProvider = z.infer<typeof LlmProviderSchema>
