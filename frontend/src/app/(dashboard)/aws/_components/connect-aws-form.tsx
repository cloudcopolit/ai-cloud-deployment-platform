'use client'

import { useRouter } from 'next/navigation'
import { useId, useState } from 'react'

import { ErrorState } from '@/components/app/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { apiFetch } from '@/lib/api/client'
import type { ApiFailure } from '@/lib/api/result'
import { AwsAccountSchema, type Team } from '@/lib/api/schemas'

export function ConnectAwsForm({ teams }: { teams: Team[] }) {
  const router = useRouter()
  const id = useId()
  const [teamId, setTeamId] = useState(teams[0]?.id ?? '')
  const [accountId, setAccountId] = useState('')
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState<ApiFailure | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setFailure(null)
    const res = await apiFetch(`/teams/${teamId}/aws-accounts`, AwsAccountSchema, {
      method: 'POST',
      body: { aws_account_id: accountId.trim(), default_region: 'us-east-1' }
    })
    setBusy(false)
    if (!res.ok) return setFailure(res)
    setAccountId('')
    router.refresh()
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-team`}>Team</Label>
          <select
            id={`${id}-team`}
            value={teamId}
            onChange={(e) => setTeamId(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            {teams.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-account`}>AWS account ID</Label>
          <Input
            id={`${id}-account`}
            required
            inputMode="numeric"
            pattern="\d{12}"
            placeholder="12 digits"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
          />
        </div>
        <Button type="submit" disabled={busy || !teamId}>
          {busy ? 'Connecting…' : 'Connect AWS account'}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Region: us-east-1 (the only region with a price table today). CloudPilot never asks for or stores AWS keys of your
        account.
      </p>
      {failure ? <ErrorState failure={failure} /> : null}
    </form>
  )
}
