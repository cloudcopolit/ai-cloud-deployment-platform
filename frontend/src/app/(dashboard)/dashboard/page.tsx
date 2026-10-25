import Link from 'next/link'
import { Suspense } from 'react'
import { FolderGit2 } from 'lucide-react'

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

  return (
    <div className="space-y-8">
      <section aria-labelledby="new-project" className="space-y-3 rounded-xl border p-4">
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
                      className="block h-full rounded-xl border p-4 hover:border-primary/60 hover:bg-muted/40"
                    >
                      <span className="flex items-center gap-2 font-medium">
                        <FolderGit2 className="size-4 text-muted-foreground" aria-hidden />
                        {p.name}
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
