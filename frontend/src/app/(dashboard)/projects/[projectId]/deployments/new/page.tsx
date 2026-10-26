import Link from 'next/link'
import { Suspense } from 'react'

import { AgentAvatar } from '@/components/agents/agent-avatar'
import { PageHeader } from '@/components/app/page-header'
import { CapabilityBadge, ErrorState, Notice } from '@/components/app/states'
import { Skeleton } from '@/components/ui/skeleton'
import { AGENTS } from '@/lib/agents'
import { apiGet } from '@/lib/api/server'
import {
  ArchitecturePlanSchema,
  ArchitectureVersionSchema,
  AwsAccountSchema,
  ProjectSchema,
  TeamSchema
} from '@/lib/api/schemas'
import { formatUsd } from '@/lib/format'
import { DeployForm } from './_components/deploy-form'

export const metadata = { title: 'Plan a deployment' }

type Params = Promise<{ projectId: string }>
type Search = Promise<{ arch?: string; v?: string }>

export default function NewDeploymentPage({ params, searchParams }: { params: Params; searchParams: Search }) {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full rounded-2xl" />}>
      <NewDeployment params={params} searchParams={searchParams} />
    </Suspense>
  )
}

async function NewDeployment({ params, searchParams }: { params: Params; searchParams: Search }) {
  const [{ projectId }, { arch, v }] = await Promise.all([params, searchParams])
  if (!arch || !v) {
    return (
      <Notice tone="warning" title="Choose an architecture first">
        Open an architecture version and use “Deploy this architecture”.
      </Notice>
    )
  }
  const [version, project, teams] = await Promise.all([
    apiGet(`/architectures/${encodeURIComponent(arch)}/versions/${encodeURIComponent(v)}`, ArchitectureVersionSchema),
    apiGet(`/projects/${projectId}`, ProjectSchema),
    apiGet('/teams', TeamSchema.array())
  ])
  if (!version.ok) return <ErrorState failure={version} />
  if (!project.ok) return <ErrorState failure={project} />
  const plan = ArchitecturePlanSchema.safeParse(version.data.architecture_data)
  const role = teams.ok ? teams.data.find((t) => t.id === project.data.team_id)?.role : undefined
  const canAdmin = role === 'OWNER' || role === 'ADMIN'
  const accounts = await apiGet(`/teams/${project.data.team_id}/aws-accounts`, AwsAccountSchema.array())
  const active = accounts.ok ? accounts.data.filter((a) => a.status === 'ACTIVE') : []
  const architectureHref = `/projects/${projectId}/architectures/${arch}/versions/${v}`

  return (
    <>
      <PageHeader
        title="Plan a deployment"
        crumbs={[
          { label: 'Overview', href: '/dashboard' },
          { label: project.data.name, href: `/projects/${projectId}` },
          { label: `Architecture v${v}`, href: architectureHref },
          { label: 'Deploy' }
        ]}
        description={
          <span className="flex flex-wrap items-center gap-2">
            OpenTofu plans the architecture in your AWS account; you approve the exact plan before anything is created.
            <CapabilityBadge level="REAL" />
          </span>
        }
      />

      {!plan.success || !plan.data.automated ? (
        <Notice tone="warning" title="This architecture cannot be deployed">
          Only automated archetypes are deployable. <Link href={architectureHref} className="underline">Back to the architecture</Link>.
        </Notice>
      ) : !canAdmin ? (
        <Notice tone="warning" title="ADMIN or OWNER role required">
          Planning a deployment uses the team&apos;s AWS account, so it needs the ADMIN or OWNER role.
        </Notice>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
          <section className="space-y-4 rounded-2xl border bg-card p-5">
            <div className="flex items-start gap-3">
              <AgentAvatar agent={AGENTS.DEPLOYMENT} size="lg" />
              <div>
                <p className="font-display text-lg font-semibold">Deployment engine</p>
                <p className="text-sm text-muted-foreground">
                  Deterministic OpenTofu from CloudPilot&apos;s module library, run in an isolated runner with short-lived
                  credentials. No language model takes part.
                </p>
              </div>
            </div>
            {active.length === 0 ? (
              <Notice tone="warning" title="No verified AWS account">
                Connect and verify an AWS account first: <Link href="/aws" className="underline">AWS accounts</Link>.
              </Notice>
            ) : (
              <DeployForm projectId={projectId} versionId={version.data.id} accounts={active} />
            )}
          </section>

          <aside className="h-fit space-y-3 rounded-2xl border bg-card p-4 text-sm">
            <p className="font-semibold">What will be planned</p>
            <ul className="space-y-1 text-muted-foreground">
              {plan.data.components.map((c) => (
                <li key={c.id} className="flex justify-between gap-2">
                  <span className="font-mono text-xs">{c.id}</span>
                  <span className="text-xs">{c.type.replaceAll('_', ' ')}</span>
                </li>
              ))}
            </ul>
            <p className="border-t pt-3">
              Architecture estimate <span className="font-mono">{formatUsd(plan.data.cost.monthly_total)}</span>/month
              <span className="block text-xs text-muted-foreground">
                pricing as of {plan.data.cost.pricing_as_of}; the plan step re-prices what OpenTofu will really create
              </span>
            </p>
          </aside>
        </div>
      )}
    </>
  )
}
