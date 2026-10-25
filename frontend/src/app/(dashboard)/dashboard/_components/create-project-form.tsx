'use client'

import { useRouter } from 'next/navigation'
import { useId, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { apiFetch } from '@/lib/api/client'
import { ProjectSchema, type Team } from '@/lib/api/schemas'

export function CreateProjectForm({ teams }: { teams: Team[] }) {
  const router = useRouter()
  const nameId = useId()
  const teamId = useId()
  const errorId = useId()
  const allowed = teams.filter((t) => t.role !== 'MEMBER')
  const [team, setTeam] = useState(allowed[0]?.id ?? '')
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (allowed.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Creating projects needs the ADMIN or OWNER role in a team.
      </p>
    )
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const res = await apiFetch(`/teams/${team}/projects`, ProjectSchema, {
      method: 'POST',
      body: { name: name.trim() }
    })
    setBusy(false)
    if (!res.ok) {
      setError(res.message)
      return
    }
    router.push(`/projects/${res.data.id}`)
    router.refresh()
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3" aria-describedby={error ? errorId : undefined}>
      {allowed.length > 1 ? (
        <div className="space-y-1.5">
          <Label htmlFor={teamId}>Team</Label>
          <select
            id={teamId}
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            className="h-9 rounded-lg border border-input bg-background px-2 text-sm"
          >
            {allowed.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
      ) : null}
      <div className="min-w-56 flex-1 space-y-1.5">
        <Label htmlFor={nameId}>Project name</Label>
        <Input
          id={nameId}
          required
          maxLength={255}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. delivery-plus"
          aria-invalid={error ? true : undefined}
        />
      </div>
      <Button type="submit" size="lg" disabled={busy || !name.trim()}>
        {busy ? 'Creating…' : 'Create project'}
      </Button>
      {error ? (
        <p id={errorId} role="alert" className="w-full text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </form>
  )
}
