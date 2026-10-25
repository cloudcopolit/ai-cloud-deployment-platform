import { describe, expect, it } from 'vitest'
import {
  AnalysisJobSchema,
  ArchitectureVersionSchema,
  AWSAccountSchema,
  DeploymentSchema,
  ApprovalSchema,
} from './pipeline'

describe('Pipeline Validations', () => {
  it('validates a successful analysis job schema', () => {
    const valid = {
      id: 'a1b2c3d4-1111-2222-3333-444455556666',
      repository_id: 'b1b2c3d4-1111-2222-3333-444455556666',
      commit_id: 'c1b2c3d4-1111-2222-3333-444455556666',
      commit_sha: 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
      status: 'SUCCESS',
      created_at: new Date().toISOString(),
      services_count: 1,
      report: {
        services: [{ name: 'api', service_type: 'api', port: 8000, path: '.' }],
      },
    }

    const parsed = AnalysisJobSchema.parse(valid)
    expect(parsed.status).toBe('SUCCESS')
    expect(parsed.services_count).toBe(1)
  })

  it('validates architecture version schema with cost math', () => {
    const valid = {
      id: 'd1b2c3d4-1111-2222-3333-444455556666',
      architecture_id: 'e1b2c3d4-1111-2222-3333-444455556666',
      version_number: 1,
      status: 'VALIDATED',
      created_at: new Date().toISOString(),
      monthly_cost: 52.0,
      architecture_data: {
        components: [{ id: 'vpc', type: 'vpc' }],
        cost: { monthly_total: 52.0 },
      },
    }

    const parsed = ArchitectureVersionSchema.parse(valid)
    expect(parsed.version_number).toBe(1)
    expect(parsed.monthly_cost).toBe(52.0)
  })

  it('validates AWS Account with external ID', () => {
    const valid = {
      id: 'f1b2c3d4-1111-2222-3333-444455556666',
      team_id: '01b2c3d4-1111-2222-3333-444455556666',
      aws_account_id: '123456789012',
      role_arn: 'arn:aws:iam::123456789012:role/CloudPilotDeploymentRole',
      external_id: 'cp-abc123456789',
      default_region: 'us-east-1',
      status: 'ACTIVE',
      connected_at: new Date().toISOString(),
    }

    const parsed = AWSAccountSchema.parse(valid)
    expect(parsed.aws_account_id).toBe('123456789012')
    expect(parsed.status).toBe('ACTIVE')
  })

  it('validates Human Approval and full Deployment lifecycle', () => {
    const approval = ApprovalSchema.parse({
      id: '11b2c3d4-1111-2222-3333-444455556666',
      requested_by: '21b2c3d4-1111-2222-3333-444455556666',
      approved_by: '31b2c3d4-1111-2222-3333-444455556666',
      status: 'APPROVED',
      reason: 'Architecture reviewed and signed off',
      requested_at: new Date().toISOString(),
      decided_at: new Date().toISOString(),
    })
    expect(approval.status).toBe('APPROVED')

    const deployment = DeploymentSchema.parse({
      id: '41b2c3d4-1111-2222-3333-444455556666',
      project_id: '51b2c3d4-1111-2222-3333-444455556666',
      repository_id: '61b2c3d4-1111-2222-3333-444455556666',
      commit_id: '71b2c3d4-1111-2222-3333-444455556666',
      architecture_version_id: '81b2c3d4-1111-2222-3333-444455556666',
      aws_account_id: '91b2c3d4-1111-2222-3333-444455556666',
      status: 'SUCCESS',
      trigger_type: 'MANUAL',
      created_at: new Date().toISOString(),
      live_endpoint: 'https://demo-app.cloudpilot.dev',
      approval,
      steps: [
        {
          id: 'a2b2c3d4-1111-2222-3333-444455556666',
          deployment_id: '41b2c3d4-1111-2222-3333-444455556666',
          step_type: 'VERIFY_HEALTH',
          step_order: 5,
          status: 'SUCCESS',
          created_at: new Date().toISOString(),
          output_data: { http_status: 200, latency_ms: 38 },
        },
      ],
      resources: [
        {
          id: 'b2b2c3d4-1111-2222-3333-444455556666',
          resource_type: 'AWS::EC2::VPC',
          resource_name: 'demo-vpc',
          aws_resource_id: 'vpc-12345678',
          region: 'us-east-1',
          status: 'ACTIVE',
        },
      ],
    })

    expect(deployment.status).toBe('SUCCESS')
    expect(deployment.live_endpoint).toBe('https://demo-app.cloudpilot.dev')
    expect(deployment.steps[0].status).toBe('SUCCESS')
  })
})
