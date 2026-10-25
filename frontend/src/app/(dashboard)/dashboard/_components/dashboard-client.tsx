'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import {
  FolderGit2,
  GitBranch,
  Rocket,
  Cpu,
  ArrowRight,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Sparkles,
  Layers,
  Server,
  Cloud
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CreateProjectModal } from './create-project-modal'
import { ConnectRepoModal } from './connect-repo-modal'
import { PipelineModal } from './pipeline-modal'
import { api } from '@/lib/axios-browser'

import type { User } from '@/lib/validations/auth'
import type { AvailableRepository, Project, Repository, Team } from '@/lib/validations/project'

interface DashboardClientProps {
  user: User
  initialTeams: Team[]
  initialProjects: Project[]
  availableRepos: AvailableRepository[]
}

export function DashboardClient({
  user,
  initialTeams,
  initialProjects,
  availableRepos
}: DashboardClientProps) {
  const [teams, setTeams] = useState<Team[]>(initialTeams)
  const [projects, setProjects] = useState<Project[]>(initialProjects)
  const [activeProjectId, setActiveProjectId] = useState<string | null>(
    initialProjects[0]?.id ?? null
  )
  const [projectRepos, setProjectRepos] = useState<Record<string, Repository[]>>({})
  const [loadingRepos, setLoadingRepos] = useState<boolean>(false)
  const [selectedPipelineRepo, setSelectedPipelineRepo] = useState<Repository | null>(null)


  // Fetch repositories for active project
  useEffect(() => {
    if (!activeProjectId) return

    let cancelled = false
    const fetchRepos = async () => {
      try {
        setLoadingRepos(true)
        const res = await api.get(`/projects/${activeProjectId}/repositories`)
        if (!cancelled) {
          setProjectRepos((prev) => ({ ...prev, [activeProjectId]: res.data }))
        }
      } catch (err) {
        // quiet error fallback
      } finally {
        if (!cancelled) setLoadingRepos(false)
      }
    }

    fetchRepos()
    return () => {
      cancelled = true
    }
  }, [activeProjectId])

  const handleProjectCreated = (newProject: Project) => {
    setProjects((prev) => [newProject, ...prev])
    setActiveProjectId(newProject.id)
  }

  const handleRepoConnected = (newRepo: Repository) => {
    setProjectRepos((prev) => {
      const current = prev[newRepo.project_id] ?? []
      return { ...prev, [newRepo.project_id]: [newRepo, ...current] }
    })
    setProjects((prev) =>
      prev.map((p) =>
        p.id === newRepo.project_id
          ? { ...p, repository_count: (p.repository_count ?? 0) + 1 }
          : p
      )
    )
  }

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? projects[0]
  const currentRepos = activeProject ? projectRepos[activeProject.id] ?? [] : []
  const totalRepos = projects.reduce((acc, p) => acc + (p.repository_count || 0), 0)

  return (
    <div className="space-y-8">
      {/* Top Banner / Hero */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-border/60">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <span>Welcome back, {user.name?.split(' ')[0] ?? user.github_user_id}</span>
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Analyze codebases, generate verified AWS architecture plans, and deploy with confidence.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <ConnectRepoModal
            projects={projects}
            availableRepos={availableRepos}
            preselectedProjectId={activeProject?.id}
            onRepoConnected={handleRepoConnected}
          />
          <CreateProjectModal teams={teams} onProjectCreated={handleProjectCreated} />
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4 border-border/70 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">Active Projects</span>
            <FolderGit2 className="size-4 text-primary" />
          </div>
          <div className="mt-2 text-2xl font-bold text-foreground">{projects.length}</div>
          <div className="mt-1 text-[11px] text-muted-foreground">Tenant isolated</div>
        </Card>

        <Card className="p-4 border-border/70 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">Repositories</span>
            <GitBranch className="size-4 text-[#19D3C5]" />
          </div>
          <div className="mt-2 text-2xl font-bold text-foreground">
            {Math.max(totalRepos, currentRepos.length)}
          </div>
          <div className="mt-1 text-[11px] text-muted-foreground">Pinned commits</div>
        </Card>

        <Card className="p-4 border-border/70 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">AI Architect</span>
            <Cpu className="size-4 text-[#2F6BFF]" />
          </div>
          <div className="mt-2 text-2xl font-bold text-foreground">Active</div>
          <div className="mt-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            Deterministic validation
          </div>
        </Card>

        <Card className="p-4 border-border/70 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">AWS Target</span>
            <Cloud className="size-4 text-amber-500" />
          </div>
          <div className="mt-2 text-2xl font-bold text-foreground">ECS/Fargate</div>
          <div className="mt-1 text-[11px] text-muted-foreground">Controlled execution</div>
        </Card>
      </div>

      {/* When no projects exist — Guided First-Time User Experience */}
      {projects.length === 0 ? (
        <Card className="border-border/80 border-dashed bg-muted/20">
          <CardHeader className="text-center pb-4 pt-8">
            <div className="mx-auto size-12 rounded-2xl bg-gradient-to-br from-[#2F6BFF]/20 to-[#19D3C5]/20 flex items-center justify-center border border-[#19D3C5]/30 mb-2">
              <Sparkles className="size-6 text-[#19D3C5]" />
            </div>
            <CardTitle className="text-xl">Let&apos;s deploy your first application</CardTitle>
            <CardDescription className="max-w-md mx-auto text-xs leading-relaxed">
              CloudPilot inspects your GitHub repository, identifies runtime requirements, generates a secure AWS architecture, and executes controlled deployments.
            </CardDescription>
          </CardHeader>
          <CardContent className="max-w-2xl mx-auto pb-10">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="p-4 rounded-xl border border-border/60 bg-card/60 space-y-2 text-left">
                <div className="size-6 rounded-md bg-primary/10 text-primary font-mono text-xs flex items-center justify-center font-bold">
                  1
                </div>
                <div className="text-xs font-semibold text-foreground">Create Project</div>
                <p className="text-[11px] text-muted-foreground">
                  Initialize an isolated workspace for your team and stack.
                </p>
              </div>

              <div className="p-4 rounded-xl border border-border/60 bg-card/60 space-y-2 text-left">
                <div className="size-6 rounded-md bg-[#19D3C5]/10 text-[#19D3C5] font-mono text-xs flex items-center justify-center font-bold">
                  2
                </div>
                <div className="text-xs font-semibold text-foreground">Connect Git Repo</div>
                <p className="text-[11px] text-muted-foreground">
                  Pick a verified reference app or connect your repository.
                </p>
              </div>

              <div className="p-4 rounded-xl border border-border/60 bg-card/60 space-y-2 text-left">
                <div className="size-6 rounded-md bg-[#2F6BFF]/10 text-[#2F6BFF] font-mono text-xs flex items-center justify-center font-bold">
                  3
                </div>
                <div className="text-xs font-semibold text-foreground">Deploy to AWS</div>
                <p className="text-[11px] text-muted-foreground">
                  Review generated architecture and approve Terraform plan.
                </p>
              </div>
            </div>

            <div className="flex justify-center">
              <CreateProjectModal
                teams={teams}
                onProjectCreated={handleProjectCreated}
                trigger={
                  <Button size="lg" className="gap-2 shadow-md">
                    <span>Create Your First Project</span>
                    <ArrowRight className="size-4" />
                  </Button>
                }
              />
            </div>
          </CardContent>
        </Card>
      ) : (
        /* When projects exist — Project Workspace */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Projects & Active Repositories (2 cols) */}
          <div className="lg:col-span-2 space-y-6">
            {/* Active Project Card */}
            {activeProject && (
              <Card className="border-border/70 shadow-xs overflow-hidden">
                <CardHeader className="bg-muted/15 border-b border-border/60 pb-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <CardTitle className="text-base font-semibold">
                          {activeProject.name}
                        </CardTitle>
                        <Badge variant="success" className="text-[10px] font-mono">
                          {activeProject.status}
                        </Badge>
                      </div>
                      <CardDescription className="text-xs mt-0.5">
                        {activeProject.description ?? 'Production-grade application workspace'}
                      </CardDescription>
                    </div>

                    {projects.length > 1 && (
                      <select
                        value={activeProjectId ?? ''}
                        onChange={(e) => setActiveProjectId(e.target.value)}
                        className="h-8 rounded-md border border-input bg-background px-2.5 py-1 text-xs shadow-xs"
                      >
                        {projects.map((p) => (
                          <option key={p.id} value={p.id}>
                            Switch: {p.name}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </CardHeader>

                <CardContent className="p-4 sm:p-6 space-y-5">
                  {/* Connected Repositories Section */}
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground uppercase tracking-wider">
                        <GitBranch className="size-3.5 text-primary" />
                        <span>Connected Source Code</span>
                      </div>
                      <ConnectRepoModal
                        projects={projects}
                        availableRepos={availableRepos}
                        preselectedProjectId={activeProject.id}
                        onRepoConnected={handleRepoConnected}
                      />
                    </div>

                    {loadingRepos ? (
                      <div className="py-8 text-center text-xs text-muted-foreground animate-pulse">
                        Loading connected repositories...
                      </div>
                    ) : currentRepos.length === 0 ? (
                      <div className="rounded-lg border border-dashed border-border/80 bg-muted/20 p-6 text-center space-y-3">
                        <p className="text-xs text-muted-foreground">
                          No repository connected to this project yet.
                        </p>
                        <ConnectRepoModal
                          projects={projects}
                          availableRepos={availableRepos}
                          preselectedProjectId={activeProject.id}
                          onRepoConnected={handleRepoConnected}
                          trigger={
                            <Button size="sm" variant="outline" className="gap-1.5 text-xs">
                              <Sparkles className="size-3.5 text-[#19D3C5]" />
                              <span>Select Reference Repository</span>
                            </Button>
                          }
                        />
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {currentRepos.map((repo) => (
                          <div
                            key={repo.id}
                            className="rounded-lg border border-border/70 bg-card p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs hover:border-border transition-colors"
                          >
                            <div className="space-y-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-xs text-foreground truncate">
                                  {repo.owner}/{repo.name}
                                </span>
                                <Badge variant="outline" className="text-[10px] font-mono px-1.5 py-0">
                                  {repo.deployment_branch ?? repo.default_branch}
                                </Badge>
                              </div>
                              <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                                <a
                                  href={repo.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="flex items-center gap-1 hover:text-foreground truncate"
                                >
                                  <span>{repo.url}</span>
                                  <ExternalLink className="size-3 shrink-0" />
                                </a>
                              </div>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                              <Button
                                size="sm"
                                className="gap-1.5 text-xs bg-gradient-to-r from-[#2F6BFF] to-[#19D3C5] hover:opacity-90 text-white"
                                onClick={() => setSelectedPipelineRepo(repo)}
                              >
                                <Cpu className="size-3.5" />
                                <span>Deploy to AWS</span>
                              </Button>
                            </div>

                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Quick Reference Apps Catalog */}
            <Card className="border-border/70 shadow-xs">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <Sparkles className="size-4 text-[#19D3C5]" />
                  <span>Verified Reference Applications</span>
                </CardTitle>
                <CardDescription className="text-xs">
                  Pre-configured stacks with verified Dockerfiles and health check endpoints.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-0">
                {availableRepos.slice(0, 4).map((app) => (
                  <div
                    key={app.id}
                    className="p-3 rounded-lg border border-border/60 bg-muted/20 space-y-1.5 flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-xs text-foreground">{app.name}</span>
                        {app.language && (
                          <Badge variant="outline" className="text-[9px] py-0 h-3.5">
                            {app.language}
                          </Badge>
                        )}
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-1 line-clamp-2">
                        {app.description}
                      </p>
                    </div>
                    <div className="pt-2 flex justify-end">
                      <ConnectRepoModal
                        projects={projects}
                        availableRepos={availableRepos}
                        preselectedProjectId={activeProject?.id}
                        onRepoConnected={handleRepoConnected}
                        trigger={
                          <Button variant="ghost" size="xs" className="text-xs gap-1 text-primary">
                            <span>Connect</span>
                            <ArrowRight className="size-3" />
                          </Button>
                        }
                      />
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          {/* Right Column: Deployment Pathway & AWS Readiness (1 col) */}
          <div className="space-y-6">
            {/* AWS Cloud Connection Status Card */}
            <Card className="border-border/70 shadow-xs">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <Cloud className="size-4 text-amber-500" />
                  <span>AWS Account Connection</span>
                </CardTitle>
                <CardDescription className="text-xs">
                  Cross-account IAM role assumption with secure External ID.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 pt-0 text-xs">
                <div className="rounded-lg bg-muted/40 p-3 space-y-2 border border-border/50">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground">Status</span>
                    <Badge variant="success" className="text-[10px] py-0 h-4">
                      VERIFIED SANDBOX
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground">Default Region</span>
                    <span className="font-mono text-foreground">us-east-1</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground">Target Pattern</span>
                    <span className="font-mono text-foreground">ECS Fargate + RDS</span>
                  </div>
                </div>

                <div className="text-[11px] text-muted-foreground space-y-1">
                  <div className="flex items-center gap-1.5 text-foreground font-medium">
                    <ShieldCheck className="size-3.5 text-emerald-500" />
                    <span>Least-Privilege Security Guarantee</span>
                  </div>
                  <p className="leading-relaxed">
                    Customer AWS long-lived access keys are never accepted or stored. Temporary STS credentials only.
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Controlled Pipeline Stages Card */}
            <Card className="border-border/70 shadow-xs">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <Layers className="size-4 text-primary" />
                  <span>Deployment Pipeline</span>
                </CardTitle>
                <CardDescription className="text-xs">
                  Strict human-in-the-loop governance.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5 pt-0 text-xs">
                <div className="flex items-start gap-2.5">
                  <CheckCircle2 className="size-4 text-emerald-500 mt-0.5 shrink-0" />
                  <div>
                    <div className="font-medium text-foreground">1. Repository Analysis</div>
                    <div className="text-[11px] text-muted-foreground">
                      Extract stack, runtime, ports, and blockers
                    </div>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <CheckCircle2 className="size-4 text-emerald-500 mt-0.5 shrink-0" />
                  <div>
                    <div className="font-medium text-foreground">2. Architecture Plan</div>
                    <div className="text-[11px] text-muted-foreground">
                      Produce typed, immutable AWS resource plan
                    </div>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <Clock className="size-4 text-amber-500 mt-0.5 shrink-0" />
                  <div>
                    <div className="font-medium text-foreground">3. Human Approval Gate</div>
                    <div className="text-[11px] text-muted-foreground">
                      Mandatory review before any AWS changes
                    </div>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <Server className="size-4 text-muted-foreground mt-0.5 shrink-0" />
                  <div>
                    <div className="font-medium text-foreground">4. Controlled Apply</div>
                    <div className="text-[11px] text-muted-foreground">
                      Terraform plan execution with health checks
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {selectedPipelineRepo && activeProject && (
        <PipelineModal
          repository={selectedPipelineRepo}
          projectId={activeProject.id}
          teamId={activeProject.team_id}
          open={!!selectedPipelineRepo}
          onOpenChange={(isOpen) => {
            if (!isOpen) setSelectedPipelineRepo(null)
          }}
        />
      )}
    </div>
  )
}

