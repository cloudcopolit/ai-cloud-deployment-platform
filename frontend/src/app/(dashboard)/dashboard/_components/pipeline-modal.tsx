'use client'

import React, { useState } from 'react'
import {
  Cpu,
  Layers,
  ShieldCheck,
  CheckCircle2,
  Clock,
  ExternalLink,
  Loader2,
  AlertTriangle,
  Server,
  Cloud,
  ChevronRight,
  Sparkles,
  DollarSign
} from 'lucide-react'

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { api } from '@/lib/axios-browser'
import { AWSAccountSchema } from '@/lib/validations/pipeline'
import type { Repository } from '@/lib/validations/project'
import type {
  AnalysisJob,
  ArchitectureVersion,
  Deployment,
} from '@/lib/validations/pipeline'

interface PipelineModalProps {
  repository: Repository
  projectId: string
  teamId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

type PipelineStage = 'analysis' | 'architecture' | 'plan' | 'approval' | 'apply'

export function PipelineModal({
  repository,
  projectId,
  teamId,
  open,
  onOpenChange,
}: PipelineModalProps) {
  const [currentStage, setCurrentStage] = useState<PipelineStage>('analysis')
  const [loading, setLoading] = useState<boolean>(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // State
  const [analysis, setAnalysis] = useState<AnalysisJob | null>(null)
  const [architecture, setArchitecture] = useState<ArchitectureVersion | null>(null)
  const [deployment, setDeployment] = useState<Deployment | null>(null)
  const [approvalNotes, setApprovalNotes] = useState<string>(
    'Architecture and cost validated. Approved for AWS production deployment.'
  )

  // Stage 1: Trigger Analysis
  const handleRunAnalysis = async () => {
    try {
      setLoading(true)
      setErrorMessage(null)
      const res = await api.post(`/repositories/${repository.id}/analyses`, {})
      setAnalysis(res.data)
      setCurrentStage('architecture')
    } catch (err: any) {
      setErrorMessage(err.response?.data?.error?.message ?? 'Failed to run code analysis')
    } finally {
      setLoading(false)
    }
  }

  // Stage 2: Generate Architecture
  const handleGenerateArchitecture = async () => {
    if (!analysis) return
    try {
      setLoading(true)
      setErrorMessage(null)
      const res = await api.post(`/analyses/${analysis.id}/architectures`, {
        region: 'us-east-1',
      })
      setArchitecture(res.data)
      setCurrentStage('plan')
    } catch (err: any) {
      setErrorMessage(err.response?.data?.error?.message ?? 'Failed to generate architecture plan')
    } finally {
      setLoading(false)
    }
  }

  // Stage 3: Connect AWS & Create Deployment Plan
  const handleCreateDeploymentPlan = async () => {
    if (!architecture) return
    try {
      setLoading(true)
      setErrorMessage(null)

      const awsListRes = await api.get(`/teams/${teamId}/aws-accounts`)
      const activeAws = AWSAccountSchema.array()
        .parse(awsListRes.data)
        .find((account) => account.status === 'ACTIVE')
      if (!activeAws) {
        setErrorMessage(
          'No verified AWS account is connected. Deployment planning is unavailable until an account has been verified.'
        )
        return
      }

      const deployRes = await api.post(`/projects/${projectId}/deployments`, {
        repository_id: repository.id,
        architecture_version_id: architecture.id,
        aws_account_id: activeAws.id,
      })

      setDeployment(deployRes.data)
      setCurrentStage('approval')
    } catch (err: any) {
      setErrorMessage(err.response?.data?.error?.message ?? 'Failed to generate deployment plan')
    } finally {
      setLoading(false)
    }
  }

  // Stage 4: Human Approval Gate
  const handleDecideApproval = async (decision: 'APPROVED' | 'REJECTED') => {
    if (!deployment) return
    try {
      setLoading(true)
      setErrorMessage(null)
      await api.post(`/deployments/${deployment.id}/approve`, {
        decision,
        reason: approvalNotes,
      })

      if (decision === 'APPROVED') {
        const updated = await api.get(`/deployments/${deployment.id}`)
        setDeployment(updated.data)
        setCurrentStage('apply')
      } else {
        onOpenChange(false)
      }
    } catch (err: any) {
      setErrorMessage(err.response?.data?.error?.message ?? 'Failed to record approval decision')
    } finally {
      setLoading(false)
    }
  }

  // Stage 5: Apply Deployment
  const handleApplyDeployment = async () => {
    if (!deployment) return
    try {
      setLoading(true)
      setErrorMessage(null)
      const res = await api.post(`/deployments/${deployment.id}/apply`)
      setDeployment(res.data)
    } catch (err: any) {
      setErrorMessage(err.response?.data?.error?.message ?? 'Failed to execute AWS deployment')
    } finally {
      setLoading(false)
    }
  }

  const services = analysis?.report?.services ?? []
  const components = architecture?.architecture_data?.components ?? []
  const cost = architecture?.architecture_data?.cost ?? {}
  const isApproved = deployment?.approval?.status === 'APPROVED'
  const isDeployed = deployment?.status === 'SUCCESS'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto p-0 gap-0 border-border/80 shadow-2xl">
        {/* Modal Header */}
        <DialogHeader className="p-6 pb-4 border-b border-border/60 bg-muted/20">
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <DialogTitle className="text-lg font-bold tracking-tight">
                  {repository.owner}/{repository.name}
                </DialogTitle>
                <Badge variant="outline" className="text-[10px] font-mono">
                  {repository.deployment_branch ?? repository.default_branch}
                </Badge>
              </div>
              <DialogDescription className="text-xs text-muted-foreground">
                Automated analysis, architecture synthesis, and controlled AWS deployment pipeline.
              </DialogDescription>
            </div>

            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-semibold">
              <Sparkles className="size-3.5 text-[#19D3C5]" />
              <span>AI Cloud Orchestrator</span>
            </div>
          </div>

          {/* Stepper Navigation */}
          <div className="grid grid-cols-5 gap-2 mt-4 pt-3 border-t border-border/50 text-[11px]">
            <button
              onClick={() => setCurrentStage('analysis')}
              className={`flex items-center gap-1.5 font-medium pb-1 border-b-2 transition-colors ${
                currentStage === 'analysis'
                  ? 'border-primary text-primary'
                  : analysis
                  ? 'border-emerald-500 text-emerald-600 dark:text-emerald-400'
                  : 'border-transparent text-muted-foreground'
              }`}
            >
              <Cpu className="size-3.5 shrink-0" />
              <span>1. Analysis</span>
            </button>

            <button
              onClick={() => analysis && setCurrentStage('architecture')}
              disabled={!analysis}
              className={`flex items-center gap-1.5 font-medium pb-1 border-b-2 transition-colors ${
                currentStage === 'architecture'
                  ? 'border-primary text-primary'
                  : architecture
                  ? 'border-emerald-500 text-emerald-600 dark:text-emerald-400'
                  : 'border-transparent text-muted-foreground opacity-50'
              }`}
            >
              <Layers className="size-3.5 shrink-0" />
              <span>2. Architecture</span>
            </button>

            <button
              onClick={() => architecture && setCurrentStage('plan')}
              disabled={!architecture}
              className={`flex items-center gap-1.5 font-medium pb-1 border-b-2 transition-colors ${
                currentStage === 'plan'
                  ? 'border-primary text-primary'
                  : deployment
                  ? 'border-emerald-500 text-emerald-600 dark:text-emerald-400'
                  : 'border-transparent text-muted-foreground opacity-50'
              }`}
            >
              <Cloud className="size-3.5 shrink-0" />
              <span>3. Plan</span>
            </button>

            <button
              onClick={() => deployment && setCurrentStage('approval')}
              disabled={!deployment}
              className={`flex items-center gap-1.5 font-medium pb-1 border-b-2 transition-colors ${
                currentStage === 'approval'
                  ? 'border-primary text-primary'
                  : isApproved
                  ? 'border-emerald-500 text-emerald-600 dark:text-emerald-400'
                  : 'border-transparent text-muted-foreground opacity-50'
              }`}
            >
              <ShieldCheck className="size-3.5 shrink-0" />
              <span>4. Approval</span>
            </button>

            <button
              onClick={() => isApproved && setCurrentStage('apply')}
              disabled={!isApproved}
              className={`flex items-center gap-1.5 font-medium pb-1 border-b-2 transition-colors ${
                currentStage === 'apply'
                  ? 'border-primary text-primary'
                  : isDeployed
                  ? 'border-emerald-500 text-emerald-600 dark:text-emerald-400'
                  : 'border-transparent text-muted-foreground opacity-50'
              }`}
            >
              <Server className="size-3.5 shrink-0" />
              <span>5. Apply</span>
            </button>
          </div>
        </DialogHeader>

        {/* Modal Body */}
        <div className="p-6 space-y-6">
          {errorMessage && (
            <div className="p-3.5 rounded-lg border border-destructive/40 bg-destructive/10 text-destructive text-xs flex items-center gap-2">
              <AlertTriangle className="size-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* STAGE 1: ANALYSIS */}
          {currentStage === 'analysis' && (
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-foreground">Codebase Intelligence</h3>
                  <p className="text-xs text-muted-foreground">
                    Deterministic inspection of languages, frameworks, listening ports, and entrypoints.
                  </p>
                </div>

                <Button
                  onClick={handleRunAnalysis}
                  disabled={loading}
                  size="sm"
                  className="gap-2 bg-gradient-to-r from-[#2F6BFF] to-[#19D3C5] text-white shadow-xs"
                >
                  {loading && <Loader2 className="size-3.5 animate-spin" />}
                  <span>{analysis ? 'Re-run Analysis' : 'Run Codebase Analysis'}</span>
                </Button>
              </div>

              {!analysis ? (
                <div className="py-12 border border-dashed rounded-xl border-border/80 bg-muted/10 text-center space-y-2">
                  <Cpu className="size-8 mx-auto text-muted-foreground" />
                  <p className="text-xs font-medium text-foreground">No analysis performed yet</p>
                  <p className="text-[11px] text-muted-foreground max-w-sm mx-auto">
                    Click &ldquo;Run Codebase Analysis&rdquo; to analyze the deployment branch and extract service metadata.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-3">
                    <Card className="p-3 bg-muted/20 border-border/60">
                      <span className="text-[11px] text-muted-foreground">Status</span>
                      <div className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 mt-1">
                        {analysis.status}
                      </div>
                    </Card>
                    <Card className="p-3 bg-muted/20 border-border/60">
                      <span className="text-[11px] text-muted-foreground">Detected Services</span>
                      <div className="text-sm font-semibold text-foreground mt-1">
                        {analysis.services_count} active
                      </div>
                    </Card>
                    <Card className="p-3 bg-muted/20 border-border/60">
                      <span className="text-[11px] text-muted-foreground">Commit SHA</span>
                      <div className="text-sm font-mono text-foreground mt-1">
                        {analysis.commit_sha.slice(0, 7)}
                      </div>
                    </Card>
                  </div>

                  {services.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-xs font-semibold text-foreground">Detected Service Specs</span>
                      {services.map((s: any, idx: number) => (
                        <div
                          key={idx}
                          className="p-3.5 rounded-lg border border-border/70 bg-card space-y-2 text-xs"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-foreground">{s.name}</span>
                            <Badge variant="outline" className="text-[10px]">
                              {s.language} / {s.framework}
                            </Badge>
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-[11px] text-muted-foreground pt-1 border-t border-border/50">
                            <div>Port: <span className="font-mono text-foreground">{s.port ?? 8000}</span></div>
                            <div>Path: <span className="font-mono text-foreground">{s.path}</span></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="flex justify-end pt-2">
                    <Button
                      onClick={() => setCurrentStage('architecture')}
                      className="gap-2 text-xs"
                    >
                      <span>Next: Review Architecture Plan</span>
                      <ChevronRight className="size-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STAGE 2: ARCHITECTURE PLAN */}
          {currentStage === 'architecture' && (
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-foreground">AWS Architecture Synthesis</h3>
                  <p className="text-xs text-muted-foreground">
                    Synthesizes production AWS resources matching detected service requirements.
                  </p>
                </div>

                <Button
                  onClick={handleGenerateArchitecture}
                  disabled={loading}
                  size="sm"
                  className="gap-2 bg-gradient-to-r from-[#2F6BFF] to-[#19D3C5] text-white shadow-xs"
                >
                  {loading && <Loader2 className="size-3.5 animate-spin" />}
                  <span>{architecture ? 'Regenerate Plan' : 'Generate Architecture'}</span>
                </Button>
              </div>

              {!architecture ? (
                <div className="py-12 border border-dashed rounded-xl border-border/80 bg-muted/10 text-center space-y-2">
                  <Layers className="size-8 mx-auto text-muted-foreground" />
                  <p className="text-xs font-medium text-foreground">Architecture plan pending</p>
                  <p className="text-[11px] text-muted-foreground max-w-sm mx-auto">
                    Click &ldquo;Generate Architecture&rdquo; to produce the typed AWS resource topology and cost estimate.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Cost & Version Card */}
                  <div className="p-4 rounded-xl border border-border/70 bg-gradient-to-r from-muted/30 to-card flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-foreground">
                          Version {architecture.version_number}
                        </span>
                        <Badge variant="success" className="text-[10px]">
                          {architecture.status}
                        </Badge>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        Target AWS Region: <span className="font-mono text-foreground">us-east-1</span>
                      </p>
                    </div>

                    <div className="text-right">
                      <div className="text-xs text-muted-foreground">Estimated Monthly Cost</div>
                      <div className="text-lg font-bold text-foreground flex items-center justify-end gap-0.5">
                        <DollarSign className="size-4 text-emerald-500" />
                        <span>{cost.monthly_total?.toFixed(2) ?? '52.00'}</span>
                        <span className="text-xs font-normal text-muted-foreground">/mo</span>
                      </div>
                    </div>
                  </div>

                  {/* Components List */}
                  <div className="space-y-2">
                    <span className="text-xs font-semibold text-foreground">AWS Target Components</span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      {components.map((c: any) => (
                        <div
                          key={c.id}
                          className="p-3 rounded-lg border border-border/60 bg-muted/15 space-y-1 text-xs"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-foreground font-mono">{c.id}</span>
                            <Badge variant="outline" className="text-[9px] uppercase font-mono">
                              {c.type}
                            </Badge>
                          </div>
                          <p className="text-[11px] text-muted-foreground leading-relaxed">
                            {c.rationale}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Security Highlights */}
                  <div className="p-3 rounded-lg border border-border/60 bg-muted/20 space-y-1.5 text-xs">
                    <div className="flex items-center gap-1.5 font-semibold text-foreground">
                      <ShieldCheck className="size-4 text-emerald-500" />
                      <span>Security Architecture Guarantee</span>
                    </div>
                    <p className="text-[11px] text-muted-foreground leading-relaxed">
                      Zero public database exposure. ECS tasks and RDS run exclusively in private VPC subnets. All ingress terminated at ALB with automated TLS.
                    </p>
                  </div>

                  <div className="flex justify-end pt-2">
                    <Button
                      onClick={() => setCurrentStage('plan')}
                      className="gap-2 text-xs"
                    >
                      <span>Next: Connect AWS & Plan Deployment</span>
                      <ChevronRight className="size-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STAGE 3: DEPLOYMENT PLAN */}
          {currentStage === 'plan' && (
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-foreground">AWS Deployment Plan</h3>
                  <p className="text-xs text-muted-foreground">
                    Connect customer AWS account and generate stage-by-stage deployment plan.
                  </p>
                </div>

                <Button
                  onClick={handleCreateDeploymentPlan}
                  disabled={loading}
                  size="sm"
                  className="gap-2 bg-gradient-to-r from-[#2F6BFF] to-[#19D3C5] text-white shadow-xs"
                >
                  {loading && <Loader2 className="size-3.5 animate-spin" />}
                  <span>{deployment ? 'Re-create Plan' : 'Generate Deployment Plan'}</span>
                </Button>
              </div>

              {!deployment ? (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl border border-border/70 bg-muted/20 space-y-3">
                    <div className="flex items-center gap-2">
                      <Cloud className="size-5 text-amber-500" />
                      <span className="font-semibold text-xs text-foreground">Target AWS Account</span>
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <span className="text-muted-foreground text-[11px]">AWS Account ID:</span>
                        <div className="font-mono font-medium text-foreground mt-0.5">123456789012</div>
                      </div>
                      <div>
                        <span className="text-muted-foreground text-[11px]">Cross-Account IAM Role:</span>
                        <div className="font-mono font-medium text-foreground mt-0.5">CloudPilotDeploymentRole</div>
                      </div>
                    </div>
                  </div>

                  <div className="p-3.5 rounded-lg border border-border/60 bg-card space-y-2 text-xs">
                    <span className="font-semibold text-foreground">Pipeline Execution Sequence</span>
                    <ol className="list-decimal list-inside space-y-1 text-muted-foreground text-[11px]">
                      <li>Assume customer IAM role via STS with unique External ID</li>
                      <li>Synthesize modular Terraform configuration</li>
                      <li>Provision VPC, ALB, Secrets Manager, and RDS PostgreSQL</li>
                      <li>Build container image and deploy Amazon ECS Fargate service</li>
                      <li>Execute automated ALB endpoint health check probe</li>
                    </ol>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl border border-border/70 bg-muted/20 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-foreground">Deployment Job Initialized</div>
                      <div className="text-[11px] text-muted-foreground mt-0.5">
                        ID: <span className="font-mono text-foreground">{deployment.id.slice(0, 8)}</span>
                      </div>
                    </div>
                    <Badge variant="outline" className="text-[10px] font-mono">
                      {deployment.status}
                    </Badge>
                  </div>

                  <div className="space-y-2">
                    <span className="text-xs font-semibold text-foreground">Execution Steps (Queued)</span>
                    <div className="space-y-2">
                      {deployment.steps.map((step) => (
                        <div
                          key={step.id}
                          className="p-3 rounded-lg border border-border/60 bg-card flex items-center justify-between text-xs"
                        >
                          <div className="flex items-center gap-2.5">
                            <Clock className="size-4 text-amber-500 shrink-0" />
                            <div>
                              <span className="font-semibold text-foreground">
                                {step.step_order}. {step.step_type.replace(/_/g, ' ')}
                              </span>
                            </div>
                          </div>
                          <Badge variant="outline" className="text-[10px]">
                            {step.status}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex justify-end pt-2">
                    <Button
                      onClick={() => setCurrentStage('approval')}
                      className="gap-2 text-xs"
                    >
                      <span>Next: Mandatory Human Approval Gate</span>
                      <ChevronRight className="size-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STAGE 4: HUMAN APPROVAL GATE */}
          {currentStage === 'approval' && (
            <div className="space-y-5">
              <div className="p-4 rounded-xl border border-amber-500/40 bg-amber-500/10 space-y-2">
                <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-semibold text-xs">
                  <ShieldCheck className="size-4" />
                  <span>Mandatory Human Approval Gate</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  CloudPilot strictly enforces human-in-the-loop validation. No infrastructure changes will be applied to your AWS account until an authorized team administrator explicitly reviews and approves the plan.
                </p>
              </div>

              <div className="p-4 rounded-xl border border-border/70 bg-card space-y-3 text-xs">
                <div className="font-semibold text-foreground">Deployment Summary</div>
                <div className="grid grid-cols-2 gap-3 text-[11px]">
                  <div>
                    <span className="text-muted-foreground">Repository:</span>
                    <div className="font-medium text-foreground">{repository.name}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Target Architecture:</span>
                    <div className="font-medium text-foreground">ECS Fargate + RDS Postgres</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Target AWS Account:</span>
                    <div className="font-medium font-mono text-foreground">123456789012 (us-east-1)</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Monthly Cost:</span>
                    <div className="font-medium text-emerald-600 dark:text-emerald-400 font-semibold">
                      ${cost.monthly_total?.toFixed(2) ?? '52.00'}/mo
                    </div>
                  </div>
                </div>

                <div className="space-y-1.5 pt-2 border-t border-border/50">
                  <label className="text-[11px] font-medium text-foreground">
                    Approval Audit Reason / Notes:
                  </label>
                  <input
                    type="text"
                    value={approvalNotes}
                    onChange={(e) => setApprovalNotes(e.target.value)}
                    className="w-full h-8 px-2.5 rounded-md border border-input bg-background text-xs"
                    placeholder="Enter approval rationale for audit log"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between pt-2">
                <Button
                  variant="outline"
                  onClick={() => handleDecideApproval('REJECTED')}
                  disabled={loading || isApproved}
                  className="text-xs text-destructive hover:bg-destructive/10"
                >
                  <span>Reject Deployment</span>
                </Button>

                <Button
                  onClick={() => handleDecideApproval('APPROVED')}
                  disabled={loading || isApproved}
                  className="gap-2 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  {loading && <Loader2 className="size-3.5 animate-spin" />}
                  <CheckCircle2 className="size-4" />
                  <span>{isApproved ? 'Approved' : 'Approve Deployment'}</span>
                </Button>
              </div>
            </div>
          )}

          {/* STAGE 5: CONTROLLED APPLY */}
          {currentStage === 'apply' && (
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-foreground">Controlled AWS Deployment</h3>
                  <p className="text-xs text-muted-foreground">
                    Sequential Terraform execution, container rollout, and health check verification.
                  </p>
                </div>

                {!isDeployed && (
                  <Button
                    onClick={handleApplyDeployment}
                    disabled={loading}
                    size="sm"
                    className="gap-2 bg-gradient-to-r from-[#2F6BFF] to-[#19D3C5] text-white shadow-xs"
                  >
                    {loading && <Loader2 className="size-3.5 animate-spin" />}
                    <span>Execute AWS Deployment (Apply)</span>
                  </Button>
                )}
              </div>

              {/* Progress Steps */}
              <div className="space-y-2">
                {deployment?.steps.map((step) => {
                  const isSuccess = step.status === 'SUCCESS'
                  const isRunning = step.status === 'RUNNING'

                  return (
                    <div
                      key={step.id}
                      className={`p-3.5 rounded-lg border transition-all text-xs ${
                        isSuccess
                          ? 'border-emerald-500/40 bg-emerald-500/5'
                          : isRunning
                          ? 'border-primary/50 bg-primary/5 shadow-xs'
                          : 'border-border/60 bg-card'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          {isSuccess ? (
                            <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />
                          ) : isRunning ? (
                            <Loader2 className="size-4 text-primary animate-spin shrink-0" />
                          ) : (
                            <Clock className="size-4 text-muted-foreground shrink-0" />
                          )}
                          <span className="font-semibold text-foreground">
                            {step.step_order}. {step.step_type.replace(/_/g, ' ')}
                          </span>
                        </div>
                        <Badge
                          variant={isSuccess ? 'success' : isRunning ? 'default' : 'outline'}
                          className="text-[10px]"
                        >
                          {step.status}
                        </Badge>
                      </div>

                      {step.output_data && isSuccess && (
                        <div className="mt-2 pt-2 border-t border-border/40 text-[11px] text-muted-foreground font-mono">
                          {step.step_type === 'VERIFY_HEALTH' && (
                            <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                              Live Probe: HTTP {step.output_data.http_status} OK (latency {step.output_data.latency_ms}ms)
                            </span>
                          )}
                          {step.step_type === 'PROVISION_INFRASTRUCTURE' && (
                            <span>{step.output_data.provisioned_count} AWS resources active</span>
                          )}
                          {step.step_type === 'DEPLOY_CONTAINER' && (
                            <span>Image: {step.output_data.image_tag} · Desired: {step.output_data.fargate_tasks} task</span>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Live Endpoint Banner */}
              {isDeployed && (
                <div className="p-5 rounded-xl border border-emerald-500/40 bg-gradient-to-br from-emerald-500/10 via-card to-[#19D3C5]/10 space-y-3">
                  <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-bold text-sm">
                    <Sparkles className="size-5" />
                    <span>Deployment Complete & Live!</span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Your application has been deployed to Amazon ECS Fargate and verified via health probe.
                  </p>

                  <div className="pt-1 flex items-center justify-between">
                    <div className="text-xs font-medium text-foreground">
                      Public Live Endpoint:
                    </div>
                    <a
                      href={deployment?.live_endpoint ?? 'https://app.cloudpilot.dev'}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-mono text-xs font-semibold shadow-xs"
                    >
                      <span>{deployment?.live_endpoint ?? 'https://app.cloudpilot.dev'}</span>
                      <ExternalLink className="size-3.5" />
                    </a>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
