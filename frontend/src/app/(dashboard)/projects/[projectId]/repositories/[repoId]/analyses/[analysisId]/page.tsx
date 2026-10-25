import { Suspense } from 'react'

import { PageHeader } from '@/components/app/page-header'
import { CapabilityBadge, ErrorState } from '@/components/app/states'
import { Stepper } from '@/components/app/stepper'
import { Skeleton } from '@/components/ui/skeleton'
import { apiGet } from '@/lib/api/server'
import { ActivitySchema, AnalysisJobSchema, ProjectSchema, RepositorySchema } from '@/lib/api/schemas'
import { AnalysisLive } from './_components/analysis-live'

export const metadata = { title: 'Analysis' }

type Params = Promise<{ projectId: string; repoId: string; analysisId: string }>

export default function AnalysisPage({ params }: { params: Params }) {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <AnalysisContent params={params} />
    </Suspense>
  )
}

async function AnalysisContent({ params }: { params: Params }) {
  const { projectId, repoId, analysisId } = await params
  const [job, activity, repo, project] = await Promise.all([
    apiGet(`/analyses/${analysisId}`, AnalysisJobSchema),
    apiGet(`/analyses/${analysisId}/activity`, ActivitySchema),
    apiGet(`/repositories/${repoId}`, RepositorySchema),
    apiGet(`/projects/${projectId}`, ProjectSchema)
  ])
  if (!job.ok) return <ErrorState failure={job} />
  if (!activity.ok) return <ErrorState failure={activity} />
  if (!repo.ok) return <ErrorState failure={repo} />
  const basePath = `/projects/${projectId}/repositories/${repoId}`
  const analysisState = !job.data.terminal ? 'current' : job.data.status === 'SUCCESS' ? 'done' : 'current'

  return (
    <>
      <PageHeader
        title="Repository analysis"
        crumbs={[
          { label: 'Overview', href: '/dashboard' },
          { label: project.ok ? project.data.name : 'Project', href: `/projects/${projectId}` },
          { label: repo.data.name, href: basePath },
          { label: 'Analysis' }
        ]}
        description={
          <span className="flex flex-wrap items-center gap-2">
            {repo.data.owner}/{repo.data.name} · real repository content, read through the worker
            <CapabilityBadge level="REAL" />
          </span>
        }
      />
      <Stepper
        steps={[
          { id: 'source', label: 'Source', state: 'done', href: basePath },
          { id: 'analysis', label: 'Analysis', state: analysisState },
          { id: 'architecture', label: 'Architecture', state: 'locked', reason: 'Being built (WORKLOG S4)' },
          { id: 'aws', label: 'AWS account', state: 'locked', reason: 'Needs an architecture' },
          { id: 'deploy', label: 'Plan & deploy', state: 'locked', reason: 'Needs approval' }
        ]}
      />
      <AnalysisLive initialJob={job.data} initialActivity={activity.data} basePath={basePath} />
    </>
  )
}
