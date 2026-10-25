import { Suspense } from 'react'
import { Lock, ShieldCheck } from 'lucide-react'

import { AgentAvatar } from '@/components/agents/agent-avatar'
import { ArchitectureStudio } from '@/components/architecture/studio'
import { describe } from '@/components/architecture/catalog'
import { PageHeader } from '@/components/app/page-header'
import { CapabilityBadge, ErrorState, Notice } from '@/components/app/states'
import { Stepper } from '@/components/app/stepper'
import { Skeleton } from '@/components/ui/skeleton'
import { AGENTS } from '@/lib/agents'
import { apiGet } from '@/lib/api/server'
import {
  AnalysisJobSchema,
  ArchitecturePlanSchema,
  ArchitectureVersionSchema,
  ProjectSchema,
  RepositorySchema,
  type ArchitecturePlan
} from '@/lib/api/schemas'
import { formatRelative, formatUsd } from '@/lib/format'

export const metadata = { title: 'Architecture' }

type Params = Promise<{ projectId: string; architectureId: string; version: string }>
type Search = Promise<{ build?: string }>

export default function ArchitectureVersionPage({ params, searchParams }: { params: Params; searchParams: Search }) {
  return (
    <Suspense fallback={<Skeleton className="h-[32rem] w-full" />}>
      <VersionContent params={params} searchParams={searchParams} />
    </Suspense>
  )
}

async function VersionContent({ params, searchParams }: { params: Params; searchParams: Search }) {
  const [{ projectId, architectureId, version }, { build }] = await Promise.all([params, searchParams])
  const [v, project] = await Promise.all([
    apiGet(`/architectures/${architectureId}/versions/${encodeURIComponent(version)}`, ArchitectureVersionSchema),
    apiGet(`/projects/${projectId}`, ProjectSchema)
  ])
  if (!v.ok) return <ErrorState failure={v} />
  const parsed = ArchitecturePlanSchema.safeParse(v.data.architecture_data)
  if (!parsed.success) {
    return (
      <ErrorState
        failure={{ ok: false, kind: 'invalid', code: 'PLAN_SHAPE', message: 'This architecture version does not match the plan contract.', status: 200 }}
      />
    )
  }
  const plan = parsed.data
  const analysis = v.data.source_analysis_id
    ? await apiGet(`/analyses/${v.data.source_analysis_id}`, AnalysisJobSchema)
    : null
  const repoId = analysis?.ok ? analysis.data.repository_id : null
  const repo = repoId ? await apiGet(`/repositories/${repoId}`, RepositorySchema) : null
  const basePath = repoId ? `/projects/${projectId}/repositories/${repoId}` : `/projects/${projectId}`
  const report = analysis?.ok ? analysis.data.report : null
  const context = {
    repository: repo?.ok ? `${repo.data.owner}/${repo.data.name}` : null,
    services: report ? report.services.length : null,
    dataStores: report ? report.data_stores.map((d) => d.engine) : [],
    recommendation: report?.recommendation?.method ?? null
  }

  return (
    <>
      <PageHeader
        title={`Architecture · version ${v.data.version_number}`}
        crumbs={[
          { label: 'Overview', href: '/dashboard' },
          { label: project.ok ? project.data.name : 'Project', href: `/projects/${projectId}` },
          ...(repo?.ok ? [{ label: repo.data.name, href: basePath }] : []),
          ...(analysis?.ok ? [{ label: 'Analysis', href: `${basePath}/analyses/${analysis.data.id}` }] : []),
          { label: `Architecture v${v.data.version_number}` }
        ]}
        description={
          <span className="flex flex-wrap items-center gap-2">
            {plan.components.length} components in {plan.region} · proposed {formatRelative(v.data.created_at)} ·
            status {v.data.status.toLowerCase()}
            <CapabilityBadge level="SIMULATED" />
          </span>
        }
      />
      <Stepper
        steps={[
          { id: 'source', label: 'Source', state: 'done', href: basePath },
          {
            id: 'analysis',
            label: 'Analysis',
            state: 'done',
            href: analysis?.ok ? `${basePath}/analyses/${analysis.data.id}` : undefined
          },
          { id: 'architecture', label: 'Architecture', state: 'current' },
          { id: 'aws', label: 'AWS account', state: 'locked', reason: 'Being built (WORKLOG S5)' },
          { id: 'deploy', label: 'Plan & deploy', state: 'locked', reason: 'Needs approval' }
        ]}
      />

      <section className="flex flex-wrap items-start gap-4 rounded-2xl border bg-card p-4 sm:p-5">
        <AgentAvatar agent={AGENTS.ARCHITECTURE} size="lg" />
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-display text-lg font-semibold">The Architect agent proposed this design</p>
          <p className="text-sm text-muted-foreground">
            Built from the analysis report: every component says why it is there. Nothing in AWS changes until a
            Terraform plan is shown to you and an ADMIN or OWNER approves that exact plan.
          </p>
        </div>
        <dl className="grid grid-cols-3 gap-4 text-center">
          <Stat label="Components" value={String(plan.components.length)} />
          <Stat label="Assumptions" value={String(plan.assumptions.length)} />
          <Stat label="Risks" value={String(plan.risks.length)} />
        </dl>
      </section>

      <Notice tone="warning" title="Prototype architect: same template for every repository">
        This version comes from the template-based prototype (container on ECS Fargate behind a load balancer, plus
        PostgreSQL when one is detected). Its costs are fixed illustrative figures, not prices from the AWS Price
        List. The real Architect agent is WORKLOG slice S4.
      </Notice>

      <section aria-labelledby="diagram" className="space-y-3">
        <h2 id="diagram" className="font-display text-lg font-semibold">
          Diagram
        </h2>
        <ArchitectureStudio plan={plan} context={context} autoplay={build === '1'} />
      </section>

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <ComponentsTable plan={plan} />
        <CostCard plan={plan} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="assumptions" className="space-y-3 rounded-2xl border p-4 sm:p-5">
          <h2 id="assumptions" className="font-semibold">
            Assumptions
          </h2>
          {plan.assumptions.length === 0 ? (
            <p className="text-sm text-muted-foreground">None stated.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {plan.assumptions.map((a) => (
                <li key={a.statement} className="flex items-start gap-2">
                  <span className="mt-0.5 rounded border px-1.5 font-mono text-[10px] text-muted-foreground">
                    {a.impact}
                  </span>
                  <span>
                    {a.statement}
                    {a.confirmed_by_user ? <span className="text-success"> · confirmed</span> : null}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section aria-labelledby="security" className="space-y-3 rounded-2xl border p-4 sm:p-5">
          <h2 id="security" className="flex items-center gap-2 font-semibold">
            <ShieldCheck className="size-4 text-success" aria-hidden /> Security design
          </h2>
          <dl className="space-y-2 text-sm">
            <Row label="Network">{plan.security.network_isolation}</Row>
            <Row label="Secrets">{plan.security.secrets_strategy}</Row>
            <Row label="Encryption">
              at rest {plan.security.encryption_at_rest ? 'on' : 'off'} · in transit{' '}
              {plan.security.encryption_in_transit ? 'on' : 'off'}
            </Row>
            <Row label="Public endpoints">
              {plan.security.public_endpoints.length ? plan.security.public_endpoints.join(', ') : 'none'}
            </Row>
            {plan.security.least_privilege_notes ? (
              <Row label="Least privilege">{plan.security.least_privilege_notes}</Row>
            ) : null}
          </dl>
        </section>
      </div>

      {plan.risks.length ? (
        <section aria-labelledby="risks" className="space-y-3">
          <h2 id="risks" className="font-semibold">
            Risks
          </h2>
          <ul className="space-y-2">
            {plan.risks.map((r) => (
              <li key={r.code + r.message} className="rounded-xl border p-3 text-sm">
                <span className="font-mono text-xs text-muted-foreground">
                  {r.severity} · {r.code}
                </span>
                <p>{r.message}</p>
                {r.suggested_action ? <p className="text-muted-foreground">{r.suggested_action}</p> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-dashed p-5">
        <div className="flex items-start gap-3">
          <Lock className="mt-0.5 size-5 text-muted-foreground" aria-hidden />
          <div>
            <p className="font-medium">Next: connect an AWS account</p>
            <p className="text-sm text-muted-foreground">
              Cross-account role with an External ID, verified with STS. Not built yet (WORKLOG S5).
            </p>
          </div>
        </div>
        <CapabilityBadge level="MISSING" />
      </section>
    </>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col-reverse">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-display text-2xl font-semibold">{value}</dd>
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[8rem_1fr] gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

/** The accessible alternative to the diagram: every component, its service, reason and links. */
function ComponentsTable({ plan }: { plan: ArchitecturePlan }) {
  return (
    <section aria-labelledby="components" className="min-w-0 space-y-3">
      <h2 id="components" className="font-semibold">
        Components
      </h2>
      <div className="overflow-x-auto rounded-2xl border">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Every component in the proposed architecture, as a table</caption>
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">
                Component
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                AWS service
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Why
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Depends on
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {plan.components.map((c) => (
              <tr key={c.id} className="align-top">
                <td className="px-3 py-2 font-mono text-xs">{c.id}</td>
                <td className="px-3 py-2">{describe(c).service}</td>
                <td className="px-3 py-2 text-muted-foreground">{c.rationale}</td>
                <td className="px-3 py-2 font-mono text-xs">{c.depends_on.join(', ') || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function CostCard({ plan }: { plan: ArchitecturePlan }) {
  return (
    <section aria-labelledby="cost" className="h-fit space-y-3 rounded-2xl border p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 id="cost" className="font-semibold">
          Monthly estimate
        </h2>
        <CapabilityBadge level="SIMULATED" />
      </div>
      <p className="font-display text-3xl font-semibold">
        {formatUsd(plan.cost.monthly_total)}
        <span className="text-sm font-normal text-muted-foreground"> /month</span>
      </p>
      <p className="text-xs text-muted-foreground">
        Illustrative prototype figures · pricing as of {plan.cost.pricing_as_of} · confidence{' '}
        {Math.round(plan.cost.confidence * 100)}%
      </p>
      <ul className="divide-y text-sm">
        {plan.cost.lines.map((l) => (
          <li key={l.component_id} className="flex justify-between gap-3 py-1.5">
            <span className="min-w-0">
              <span className="block font-mono text-xs">{l.component_id}</span>
              <span className="block text-xs text-muted-foreground">{l.basis}</span>
            </span>
            <span className="shrink-0 font-mono">{formatUsd(l.monthly_usd)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
