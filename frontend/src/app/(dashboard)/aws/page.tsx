import { Suspense } from 'react'

import { PageHeader } from '@/components/app/page-header'
import { CapabilityBadge, EmptyState, ErrorState } from '@/components/app/states'
import { Skeleton } from '@/components/ui/skeleton'
import { apiGet } from '@/lib/api/server'
import { AwsAccountSchema, TeamSchema } from '@/lib/api/schemas'
import { AwsAccountCard } from './_components/aws-account-card'
import { ConnectAwsForm } from './_components/connect-aws-form'

export const metadata = { title: 'AWS accounts' }

export default function AwsAccountsPage() {
  return (
    <>
      <PageHeader
        title="AWS accounts"
        description={
          <span className="flex flex-wrap items-center gap-2">
            Where CloudPilot deploys: your account, through a role you create, assumed with an External ID for one job at
            a time.
            <CapabilityBadge level="REAL" />
          </span>
        }
      />
      <Suspense fallback={<Skeleton className="h-64 w-full rounded-2xl" />}>
        <Accounts />
      </Suspense>
    </>
  )
}

async function Accounts() {
  const teams = await apiGet('/teams', TeamSchema.array())
  if (!teams.ok) return <ErrorState failure={teams} />
  const lists = await Promise.all(
    teams.data.map(async (t) => ({ team: t, accounts: await apiGet(`/teams/${t.id}/aws-accounts`, AwsAccountSchema.array()) }))
  )
  const adminTeams = teams.data.filter((t) => t.role === 'OWNER' || t.role === 'ADMIN')

  return (
    <div className="space-y-8">
      {adminTeams.length ? (
        <section aria-labelledby="connect" className="space-y-3 rounded-2xl border bg-card p-4 sm:p-5">
          <h2 id="connect" className="font-semibold">
            Connect an account
          </h2>
          <ConnectAwsForm teams={adminTeams} />
        </section>
      ) : null}

      {lists.map(({ team, accounts }) => (
        <section key={team.id} aria-labelledby={`aws-${team.id}`} className="space-y-3">
          <h2 id={`aws-${team.id}`} className="flex items-baseline gap-2 font-semibold">
            {team.name}
            <span className="font-mono text-xs font-normal text-muted-foreground">{team.role}</span>
          </h2>
          {!accounts.ok ? (
            <ErrorState failure={accounts} />
          ) : accounts.data.length === 0 ? (
            <EmptyState title="No AWS account connected">Connect one above to deploy an approved plan.</EmptyState>
          ) : (
            <ul className="space-y-4">
              {accounts.data.map((a) => (
                <AwsAccountCard key={a.id} account={a} canAdmin={team.role === 'OWNER' || team.role === 'ADMIN'} />
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  )
}
