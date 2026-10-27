'use client'

import { useRouter } from 'next/navigation'
import { useId, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

/* Seeded by `python -m app.db.seed` (backend/app/db/seed.py). */
const SEEDED = [
  { id: '1001', label: 'Alice — OWNER of Acme Startup' },
  { id: '1002', label: 'Bob — ADMIN of Acme Startup' },
  { id: '1003', label: 'Carol — MEMBER of Acme Startup' }
]

export function DevLogin() {
  const router = useRouter()
  const selectId = useId()
  const [user, setUser] = useState(SEEDED[0].id)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const res = await fetch(`${API_URL}/auth/dev-login`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ github_user_id: user })
      })
      if (!res.ok) {
        setError(
          res.status === 404
            ? 'Developer sign-in is off on the backend, or the seed data is missing.'
            : `Sign-in failed (HTTP ${res.status}).`
        )
        return
      }
      router.push('/dashboard')
      router.refresh()
    } catch {
      setError('The CloudPilot API cannot be reached.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-dashed p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-warning">Development only</p>
      <div className="space-y-1.5">
        <Label htmlFor={selectId}>Sign in as a seeded user</Label>
        <select
          id={selectId}
          value={user}
          onChange={(e) => setUser(e.target.value)}
          className="h-9 w-full rounded-lg border border-input bg-background px-2 text-sm"
        >
          {SEEDED.map((u) => (
            <option key={u.id} value={u.id}>
              {u.label}
            </option>
          ))}
        </select>
      </div>
      <Button type="submit" variant="outline" className="w-full" disabled={busy}>
        {busy ? 'Signing in…' : 'Developer sign-in'}
      </Button>
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </form>
  )
}
