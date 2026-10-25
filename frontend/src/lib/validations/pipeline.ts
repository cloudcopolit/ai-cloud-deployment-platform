import { z } from 'zod'

export const ServiceItemSchema = z.object({
  name: z.string(),
  service_type: z.string(),
  language: z.string().nullable().optional(),
  framework: z.string().nullable().optional(),
  path: z.string(),
  port: z.number().nullable().optional(),
  metadata: z.record(z.string(), z.any()).default({})
})
export type ServiceItem = z.infer<typeof ServiceItemSchema>

export const AnalysisJobSchema = z.object({
  id: z.string(),
  repository_id: z.string(),
  commit_id: z.string(),
  commit_sha: z.string(),
  status: z.string(),
  created_at: z.string(),
  started_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
  error_code: z.string().nullable().optional(),
  error_message: z.string().nullable().optional(),
  services_count: z.number().default(0),
  report: z.record(z.string(), z.any()).nullable().optional()
})
export type AnalysisJob = z.infer<typeof AnalysisJobSchema>

export const ArchitectureVersionSchema = z.object({
  id: z.string(),
  architecture_id: z.string(),
  version_number: z.number(),
  source_analysis_id: z.string().nullable().optional(),
  status: z.string(),
  architecture_data: z.record(z.string(), z.any()),
  created_by: z.string().nullable().optional(),
  created_at: z.string(),
  monthly_cost: z.number().default(0)
})
export type ArchitectureVersion = z.infer<typeof ArchitectureVersionSchema>

export const AWSAccountSchema = z.object({
  id: z.string(),
  team_id: z.string(),
  aws_account_id: z.string(),
  role_arn: z.string().nullable().optional(),
  external_id: z.string(),
  default_region: z.string(),
  status: z.string(),
  connected_at: z.string(),
  last_verified_at: z.string().nullable().optional()
})
export type AWSAccount = z.infer<typeof AWSAccountSchema>

export const DeploymentStepSchema = z.object({
  id: z.string(),
  deployment_id: z.string(),
  step_type: z.string(),
  step_order: z.number(),
  status: z.string(),
  created_at: z.string(),
  started_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
  error_code: z.string().nullable().optional(),
  error_message: z.string().nullable().optional(),
  output_data: z.record(z.string(), z.any()).nullable().optional()
})
export type DeploymentStep = z.infer<typeof DeploymentStepSchema>

export const ApprovalSchema = z.object({
  id: z.string(),
  deployment_id: z.string().nullable().optional(),
  requested_by: z.string(),
  approved_by: z.string().nullable().optional(),
  status: z.string(),
  reason: z.string().nullable().optional(),
  requested_at: z.string(),
  decided_at: z.string().nullable().optional()
})
export type Approval = z.infer<typeof ApprovalSchema>

export const InfrastructureResourceSchema = z.object({
  id: z.string(),
  resource_type: z.string(),
  resource_name: z.string(),
  aws_resource_id: z.string().nullable().optional(),
  aws_arn: z.string().nullable().optional(),
  region: z.string(),
  status: z.string()
})
export type InfrastructureResource = z.infer<typeof InfrastructureResourceSchema>

export const DeploymentSchema = z.object({
  id: z.string(),
  project_id: z.string(),
  repository_id: z.string(),
  commit_id: z.string(),
  architecture_version_id: z.string(),
  aws_account_id: z.string(),
  status: z.string(),
  trigger_type: z.string(),
  created_at: z.string(),
  started_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
  created_by: z.string().nullable().optional(),
  error_code: z.string().nullable().optional(),
  error_message: z.string().nullable().optional(),
  steps: z.array(DeploymentStepSchema).default([]),
  approval: ApprovalSchema.nullable().optional(),
  live_endpoint: z.string().nullable().optional(),
  resources: z.array(InfrastructureResourceSchema).default([])
})
export type Deployment = z.infer<typeof DeploymentSchema>
