'use client'

import { useRouter } from 'next/navigation'
import { useId, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { apiFetch } from '@/lib/api/client'
import { RepositorySchema } from '@/lib/api/schemas'

const GITHUB_URL = /^(https?:\/\/(www\.)?github\.com\/|git@github\.com:)?[A-Za-z0-9-]+\/[A-Za-z0-9._-]+(\.git)?\/?$/

export function ConnectRepositoryForm({ projectId }: { projectId: string }) {
  const router = useRouter()
  const inputId = useId()
  const hintId = useId()
  const errorId = useId()
  const [url, setUrl] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!GITHUB_URL.test(url.trim())) {
      setError('Enter a GitHub repository URL such as https://github.com/owner/repository.')
      return
    }
    setBusy(true)
    setError(null)
    const res = await apiFetch(`/projects/${projectId}/repositories`, RepositorySchema, {
      method: 'POST',
      body: { url: url.trim() }
    })
    setBusy(false)
    if (!res.ok) {
      setError(res.message)
      return
    }
    router.push(`/projects/${projectId}/repositories/${res.data.id}`)
    router.refresh()
  }

  return (
    <form onSubmit={submit} className="space-y-2" noValidate>
      <Label htmlFor={inputId}>GitHub repository URL</Label>
      <div className="flex flex-wrap gap-2">
        <Input
          id={inputId}
          className="min-w-64 flex-1 font-mono"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          placeholder="https://github.com/owner/repository"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          aria-describedby={`${hintId}${error ? ` ${errorId}` : ''}`}
          aria-invalid={error ? true : undefined}
        />
        <Button type="submit" size="lg" disabled={busy || !url.trim()}>
          {busy ? 'Reading GitHub…' : 'Connect'}
        </Button>
      </div>
      <p id={hintId} className="text-xs text-muted-foreground">
        CloudPilot reads the repository&apos;s metadata, branches and recent commits from GitHub. Source
        code is never stored.
      </p>
      {error ? (
        <p id={errorId} role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </form>
  )
}
