import Link from 'next/link'
import { Suspense } from 'react'
import { GitBranch, Lock } from 'lucide-react'

import { PageHeader } from '@/components/app/page-header'
import { EmptyState, ErrorState } from '@/components/app/states'
import { Skeleton } from '@/components/ui/skeleton'
import { apiGet } from '@/lib/api/server'
import { ProjectSchema, RepositorySchema } from '@/lib/api/schemas'
import { formatRelative } from '@/lib/format'
import { ConnectRepositoryForm } from './_components/connect-repository-form'

export const metadata = { title: 'Project' }

export default function ProjectPage({ params }: { params: Promise<{ projectId: string }> }) {
  return (
    <Suspense fallback={<Skeleton className="h-40 w-full" />}>
      <ProjectContent params={params} />
    </Suspense>
  )
}

async function ProjectContent({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  const [project, repos] = await Promise.all([
    apiGet(`/projects/${projectId}`, ProjectSchema),
    apiGet(`/projects/${projectId}/repositories`, RepositorySchema.array())
  ])
  if (!project.ok) return <ErrorState failure={project} />

  const p = project.data
  return (
    <>
      <PageHeader
        title={p.name}
        crumbs={[{ label: 'Overview', href: '/dashboard' }, { label: p.team_name ?? 'Team' }, { label: p.name }]}
        description={p.description ?? undefined}
      />

      {p.status === 'ARCHIVED' ? (
        <EmptyState title="This project is archived">It keeps its history but accepts no new work.</EmptyState>
      ) : (
        <section aria-labelledby="connect" className="space-y-3 rounded-xl border p-4">
          <h2 id="connect" className="text-sm font-medium">
            Connect a repository
          </h2>
          <ConnectRepositoryForm projectId={p.id} />
        </section>
      )}

      <section aria-labelledby="repos" className="space-y-3">
        <h2 id="repos" className="text-lg font-semibold">
          Repositories
        </h2>
        {!repos.ok ? (
          <ErrorState failure={repos} />
        ) : repos.data.length === 0 ? (
          <EmptyState title="No repositories connected">
            Paste a public GitHub URL above. CloudPilot resolves the repository, its branches and
            commits from GitHub.
          </EmptyState>
        ) : (
          <ul className="divide-y rounded-xl border">
            {repos.data.map((r) => (
              <li key={r.id}>
                <Link
                  href={`/projects/${p.id}/repositories/${r.id}`}
                  className="flex flex-wrap items-center justify-between gap-3 p-4 hover:bg-muted/40"
                >
                  <span className="min-w-0">
                    <span className="flex items-center gap-2 font-medium">
                      {r.owner}/{r.name}
                      {r.is_private ? <Lock className="size-3.5 text-muted-foreground" aria-label="Private" /> : null}
                    </span>
                    <span className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
                      <GitBranch className="size-3.5" aria-hidden />
                      deploys from <span className="font-mono">{r.deployment_branch ?? '—'}</span> ·{' '}
                      {r.branch_count} branch{r.branch_count === 1 ? '' : 'es'}
                    </span>
                  </span>
                  <span className="text-xs text-muted-foreground">
                    synced {r.last_synced_at ? formatRelative(r.last_synced_at) : 'never'}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
