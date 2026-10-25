import { Suspense } from 'react'
import { ExternalLink, Lock } from 'lucide-react'

import { PageHeader } from '@/components/app/page-header'
import { CapabilityBadge, ErrorState } from '@/components/app/states'
import { Stepper } from '@/components/app/stepper'
import { Skeleton } from '@/components/ui/skeleton'
import { apiGet } from '@/lib/api/server'
import Link from 'next/link'

import { StatusBadge } from '@/components/app/status-badge'
import {
  AnalysisJobSchema,
  BranchSchema,
  ProjectSchema,
  RepositorySchema,
  TeamSchema
} from '@/lib/api/schemas'
import { formatRelative, shortSha } from '@/lib/format'
import { SourcePicker } from './_components/source-picker'

export const metadata = { title: 'Repository' }

type Params = Promise<{ projectId: string; repoId: string }>

export default function RepositoryPage({ params }: { params: Params }) {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <RepositoryContent params={params} />
    </Suspense>
  )
}

const ACCESS_LABEL = {
  GITHUB_APP: 'read through the CloudPilot GitHub App',
  TOKEN: 'read with the configured GitHub token',
  ANONYMOUS: 'read anonymously (public repository)'
} as const

async function RepositoryContent({ params }: { params: Params }) {
  const { projectId, repoId } = await params
  const [repo, branches, project, teams, analyses] = await Promise.all([
    apiGet(`/repositories/${repoId}`, RepositorySchema),
    apiGet(`/repositories/${repoId}/branches`, BranchSchema.array()),
    apiGet(`/projects/${projectId}`, ProjectSchema),
    apiGet('/teams', TeamSchema.array()),
    apiGet(`/repositories/${repoId}/analyses?limit=10`, AnalysisJobSchema.array())
  ])
  if (!repo.ok) return <ErrorState failure={repo} />
  if (!project.ok) return <ErrorState failure={project} />
  const r = repo.data
  const role = teams.ok ? teams.data.find((t) => t.id === project.data.team_id)?.role : undefined
  const canAdmin = role === 'OWNER' || role === 'ADMIN'

  return (
    <>
      <PageHeader
        title={`${r.owner}/${r.name}`}
        crumbs={[
          { label: 'Overview', href: '/dashboard' },
          { label: project.data.name, href: `/projects/${projectId}` },
          { label: r.name }
        ]}
        description={
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {r.is_private ? (
              <span className="inline-flex items-center gap-1">
                <Lock className="size-3.5" aria-hidden /> Private
              </span>
            ) : (
              'Public'
            )}
            <span aria-hidden>·</span>
            <span>{ACCESS_LABEL[r.access_mode]}</span>
            <span aria-hidden>·</span>
            <span>synced {r.last_synced_at ? formatRelative(r.last_synced_at) : 'never'}</span>
            <CapabilityBadge level="REAL" />
          </span>
        }
        actions={
          <a
            href={r.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm hover:bg-muted"
          >
            Open on GitHub <ExternalLink className="size-3.5" aria-hidden />
          </a>
        }
      />

      <Stepper
        steps={[
          { id: 'source', label: 'Source', state: 'current' },
          { id: 'analysis', label: 'Analysis', state: 'todo' },
          { id: 'architecture', label: 'Architecture', state: 'locked', reason: 'Needs an analysis' },
          { id: 'aws', label: 'AWS account', state: 'locked', reason: 'Needs an architecture' },
          { id: 'deploy', label: 'Plan & deploy', state: 'locked', reason: 'Needs approval' }
        ]}
      />

      <section aria-labelledby="source" className="space-y-4 rounded-xl border p-4 sm:p-5">
        <div>
          <h2 id="source" className="text-lg font-semibold">
            Choose the code to analyze
          </h2>
          <p className="text-sm text-muted-foreground">
            Branches and commits come from GitHub. Pick a branch, then a commit; the branch head is
            preselected.
            {r.branches_truncated ? ' Only the first 300 branches are listed.' : ''}
          </p>
        </div>
        {branches.ok ? (
          <SourcePicker repoId={r.id} projectId={projectId} branches={branches.data} canAdmin={canAdmin} />
        ) : (
          <ErrorState failure={branches} />
        )}
      </section>

      <section aria-labelledby="history" className="space-y-3">
        <h2 id="history" className="text-lg font-semibold">
          Recent analyses
        </h2>
        {!analyses.ok ? (
          <ErrorState failure={analyses} />
        ) : analyses.data.length === 0 ? (
          <p className="text-sm text-muted-foreground">None yet.</p>
        ) : (
          <ul className="divide-y rounded-xl border">
            {analyses.data.map((a) => (
              <li key={a.id}>
                <Link
                  href={`/projects/${projectId}/repositories/${r.id}/analyses/${a.id}`}
                  className="flex flex-wrap items-center justify-between gap-3 p-3 hover:bg-muted/40"
                >
                  <span className="text-sm">
                    <span className="font-mono">{shortSha(a.commit_sha)}</span>
                    {a.branch_name ? ` on ${a.branch_name}` : ''} · {a.services_count} service
                    {a.services_count === 1 ? '' : 's'}
                    {a.parent_analysis_id ? ' · re-run with answers' : ''}
                  </span>
                  <span className="flex items-center gap-3 text-xs text-muted-foreground">
                    {formatRelative(a.created_at)}
                    <StatusBadge status={a.status} compact />
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
