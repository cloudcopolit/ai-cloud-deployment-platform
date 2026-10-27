import Link from 'next/link'
import { Suspense } from 'react'
import { ArrowRight } from 'lucide-react'

import { AgentPortrait } from '@/components/agents/agent-avatar'
import { SpriteIcon } from '@/components/brand/icons'
import { AGENT_ORDER, AGENTS } from '@/lib/agents'

import { PageHeader } from '@/components/app/page-header'
import { EmptyState, ErrorState, Notice } from '@/components/app/states'
import { Skeleton } from '@/components/ui/skeleton'
import { apiGet } from '@/lib/api/server'
import { GitHubAccessSchema, ProjectSchema, TeamSchema } from '@/lib/api/schemas'
import { CreateProjectForm } from './_components/create-project-form'

export const metadata = { title: 'Overview' }

export default function DashboardPage() {
  return (
    <>
      <PageHeader
        title="Overview"
        description="Projects in your teams. Open a project to connect a GitHub repository."
      />
      <Suspense fallback={<Skeleton className="h-16 w-full" />}>
        <AccessNotice />
      </Suspense>
      <Suspense fallback={<ProjectsSkeleton />}>
        <Projects />
      </Suspense>
    </>
  )
}

async function AccessNotice() {
  const access = await apiGet('/github/access', GitHubAccessSchema)
  if (!access.ok || access.data.app_installations) return null
  const a = access.data
  return (
    <Notice tone="info" title="Only public repositories can be connected right now">
      {a.token_configured
        ? 'CloudPilot reads public repositories with the configured GITHUB_TOKEN.'
        : `CloudPilot reads public repositories anonymously (${a.rate_limit_remaining ?? '?'} of ${a.rate_limit_limit ?? 60} GitHub API requests left this hour).`}{' '}
      Private repositories need the CloudPilot GitHub App installed on them
      {a.app_install_url ? (
        <>
          {' '}
          (
          <a className="text-primary underline" href={a.app_install_url} target="_blank" rel="noreferrer">
            install the App
          </a>
          )
        </>
      ) : null}
      .
    </Notice>
  )
}

async function Projects() {
  const [teams, projects] = await Promise.all([
    apiGet('/teams', TeamSchema.array()),
    apiGet('/projects', ProjectSchema.array())
  ])
  if (!teams.ok) return <ErrorState failure={teams} />
  if (!projects.ok) return <ErrorState failure={projects} />

  const repositories = projects.data.reduce((n, p) => n + p.repository_count, 0)

  return (
    <div className="space-y-8">
      <section className="dark relative overflow-hidden rounded-2xl bg-brand-black p-6 text-foreground sm:p-8">
        <div aria-hidden className="bg-grid absolute inset-0 opacity-30" />
        <div aria-hidden className="absolute -right-24 -top-24 size-80 rounded-full bg-brand-blue/30 blur-3xl" />
        <div className="relative flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-xl space-y-2">
            <p className="font-display text-2xl font-semibold">Welcome back.</p>
            <p className="text-sm text-muted-foreground">
              Open a project, connect a repository and start an analysis. You can watch every agent work and stop it
              at any time.
            </p>
            <div className="flex items-center gap-2 pt-2">
              {AGENT_ORDER.map((key) => (
                <AgentPortrait key={key} agent={AGENTS[key]} size="sm" />
              ))}
              <Link href="/agents" className="ml-1 inline-flex items-center gap-1 text-sm text-primary hover:underline">
                Meet the agents <ArrowRight className="size-3.5" aria-hidden />
              </Link>
            </div>
          </div>
          <dl className="grid grid-cols-3 gap-6 text-center">
            {[
              ['Teams', teams.data.length],
              ['Projects', projects.data.length],
              ['Repositories', repositories]
            ].map(([label, value]) => (
              <div key={label} className="flex flex-col-reverse">
                <dt className="text-xs text-muted-foreground">{label}</dt>
                <dd className="font-display text-3xl font-semibold">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section aria-labelledby="new-project" className="space-y-3 rounded-2xl border bg-card p-4 sm:p-5">
        <h2 id="new-project" className="text-sm font-medium">
          New project
        </h2>
        <CreateProjectForm teams={teams.data} />
      </section>

      {teams.data.map((team) => {
        const list = projects.data.filter((p) => p.team_id === team.id)
        return (
          <section key={team.id} aria-labelledby={`team-${team.id}`} className="space-y-3">
            <h2 id={`team-${team.id}`} className="flex items-baseline gap-2 text-lg font-semibold">
              {team.name}
              <span className="font-mono text-xs font-normal text-muted-foreground">
                {team.role} · {team.plan_code} plan · {team.member_count} member
                {team.member_count === 1 ? '' : 's'}
              </span>
            </h2>
            {list.length === 0 ? (
              <EmptyState title="No projects in this team yet">
                Create one above, then connect a GitHub repository to it.
              </EmptyState>
            ) : (
              <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {list.map((p) => (
                  <li key={p.id}>
                    <Link
                      href={`/projects/${p.id}`}
                      className="group block h-full rounded-2xl border bg-card p-4 transition hover:-translate-y-0.5 hover:border-primary/60 hover:shadow-md"
                    >
                      <span className="flex items-center gap-2.5 font-medium">
                        <span className="bg-brand-gradient grid size-8 place-items-center rounded-lg text-white">
                          <SpriteIcon name="ui-folder" className="size-4" />
                        </span>
                        {p.name}
                        <ArrowRight
                          className="ml-auto size-4 text-muted-foreground opacity-0 transition group-hover:opacity-100"
                          aria-hidden
                        />
                      </span>
                      {p.description ? (
                        <span className="mt-1 line-clamp-2 block text-sm text-muted-foreground">
                          {p.description}
                        </span>
                      ) : null}
                      <span className="mt-3 block font-mono text-xs text-muted-foreground">
                        {p.repository_count} repositor{p.repository_count === 1 ? 'y' : 'ies'}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )
      })}
    </div>
  )
}

function ProjectsSkeleton() {
  return (
    <div role="status" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <span className="sr-only">Loading projects…</span>
      {Array.from({ length: 3 }, (_, i) => (
        <Skeleton key={i} className="h-28 w-full rounded-xl" />
      ))}
    </div>
  )
}
