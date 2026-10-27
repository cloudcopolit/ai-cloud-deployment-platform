import { Suspense } from 'react'

import { PageHeader } from '@/components/app/page-header'
import { CapabilityBadge, ErrorState } from '@/components/app/states'
import { Skeleton } from '@/components/ui/skeleton'
import { apiGet } from '@/lib/api/server'
import { AuditEntrySchema, DeploymentSchema, ProjectSchema, TeamSchema } from '@/lib/api/schemas'
import { formatRelative } from '@/lib/format'
import { DeploymentLive } from './_components/deployment-live'

export const metadata = { title: 'Deployment' }

type Params = Promise<{ projectId: string; deploymentId: string }>

export default function DeploymentPage({ params }: { params: Params }) {
  return (
    <Suspense fallback={<Skeleton className="h-[32rem] w-full rounded-2xl" />}>
      <DeploymentContent params={params} />
    </Suspense>
  )
}

async function DeploymentContent({ params }: { params: Params }) {
  const { projectId, deploymentId } = await params
  const [deployment, audit, project, teams] = await Promise.all([
    apiGet(`/deployments/${deploymentId}`, DeploymentSchema),
    apiGet(`/deployments/${deploymentId}/audit`, AuditEntrySchema.array()),
    apiGet(`/projects/${projectId}`, ProjectSchema),
    apiGet('/teams', TeamSchema.array())
  ])
  if (!deployment.ok) return <ErrorState failure={deployment} />
  if (!project.ok) return <ErrorState failure={project} />
  const role = teams.ok ? teams.data.find((t) => t.id === project.data.team_id)?.role : undefined

  return (
    <>
      <PageHeader
        title={`Deployment ${deployment.data.id.slice(0, 8)}`}
        crumbs={[
          { label: 'Overview', href: '/dashboard' },
          { label: project.data.name, href: `/projects/${projectId}` },
          { label: 'Deployment' }
        ]}
        description={
          <span className="flex flex-wrap items-center gap-2">
            {deployment.data.region} · requested {formatRelative(deployment.data.created_at)} · real AWS, through an
            assumed role
            <CapabilityBadge level="REAL" />
          </span>
        }
      />
      <DeploymentLive
        initial={deployment.data}
        initialAudit={audit.ok ? audit.data : []}
        canAdmin={role === 'OWNER' || role === 'ADMIN'}
      />
    </>
  )
}
