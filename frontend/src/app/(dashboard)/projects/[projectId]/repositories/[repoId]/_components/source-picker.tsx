'use client'

import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { useCallback, useEffect, useId, useState } from 'react'
import { Play, RefreshCw } from 'lucide-react'

import { ErrorState } from '@/components/app/states'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { apiFetch } from '@/lib/api/client'
import type { ApiFailure } from '@/lib/api/result'
import {
  AnalysisJobSchema,
  BranchSchema,
  CommitSchema,
  RepositorySchema,
  type Branch,
  type Commit
} from '@/lib/api/schemas'
import { commitTitle, formatRelative, shortSha } from '@/lib/format'

type Props = {
  repoId: string
  projectId: string
  branches: Branch[]
  canAdmin: boolean
}

export function SourcePicker({ repoId, projectId, branches: initialBranches, canAdmin }: Props) {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const branchSelectId = useId()
  const [branches, setBranches] = useState(initialBranches)
  const deployment = branches.find((b) => b.is_deployment_branch)?.name ?? branches[0]?.name ?? ''
  // Local state answers clicks at once; the URL mirrors it so a selection can be shared.
  const [branch, setBranch] = useState(params.get('branch') ?? deployment)
  const [sha, setSha] = useState<string | null>(params.get('sha'))

  const [commits, setCommits] = useState<Commit[] | null>(null)
  const [failure, setFailure] = useState<ApiFailure | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)

  const setParams = useCallback(
    (next: Record<string, string | null>) => {
      const q = new URLSearchParams(params.toString())
      for (const [k, v] of Object.entries(next)) {
        if (v === null) q.delete(k)
        else q.set(k, v)
      }
      router.replace(`${pathname}?${q.toString()}`, { scroll: false })
    },
    [params, pathname, router]
  )

  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (!branch) return
    const controller = new AbortController()
    const url = (refresh: boolean) =>
      `/repositories/${repoId}/commits?branch=${encodeURIComponent(branch)}&refresh=${refresh}&limit=20`
    // Cached commits first; GitHub only when nothing is cached or the user asked to sync.
    // Anonymous GitHub access allows 60 API requests per hour.
    const load = async () => {
      let res = await apiFetch(url(refreshKey > 0), CommitSchema.array(), { signal: controller.signal })
      if (res.ok && res.data.length === 0 && refreshKey === 0) {
        res = await apiFetch(url(true), CommitSchema.array(), { signal: controller.signal })
      }
      if (res.ok) {
        setCommits(res.data)
        setFailure(null)
      } else {
        setFailure(res)
        setCommits([])
      }
    }
    load().catch(() => undefined) // aborted by a newer branch choice
    return () => controller.abort()
  }, [repoId, branch, refreshKey])

  const chosen = commits?.find((c) => c.sha === sha) ?? commits?.[0] ?? null

  async function sync() {
    setSyncing(true)
    setNotice(null)
    const res = await apiFetch(`/repositories/${repoId}/sync`, RepositorySchema, { method: 'POST' })
    if (res.ok) {
      const list = await apiFetch(`/repositories/${repoId}/branches`, BranchSchema.array())
      if (list.ok) setBranches(list.data)
      setCommits(null)
      setRefreshKey((k) => k + 1)
      setNotice(`Synced ${res.data.branch_count} branches and the latest commits from GitHub.`)
      router.refresh()
    } else {
      setFailure(res)
    }
    setSyncing(false)
  }

  async function analyze() {
    if (!chosen) return
    setStarting(true)
    setFailure(null)
    // One key per click: a double submit or a retried request reuses the same job.
    const res = await apiFetch(`/repositories/${repoId}/analyses`, AnalysisJobSchema, {
      method: 'POST',
      body: { branch, commit_sha: chosen.sha },
      headers: { 'Idempotency-Key': crypto.randomUUID() }
    })
    if (!res.ok) {
      setFailure(res)
      setStarting(false)
      return
    }
    router.push(`/projects/${projectId}/repositories/${repoId}/analyses/${res.data.id}`)
  }

  async function makeDeploymentBranch() {
    const res = await apiFetch(`/repositories/${repoId}/deployment-branch`, BranchSchema, {
      method: 'PUT',
      body: { branch_name: branch }
    })
    if (res.ok) {
      setBranches((bs) => bs.map((b) => ({ ...b, is_deployment_branch: b.name === branch })))
      setNotice(`"${branch}" is now the deployment branch.`)
      router.refresh()
    } else {
      setFailure(res)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor={branchSelectId}>Branch</Label>
          <select
            id={branchSelectId}
            value={branch}
            onChange={(e) => {
              setCommits(null)
              setBranch(e.target.value)
              setSha(null)
              setParams({ branch: e.target.value, sha: null })
            }}
            className="h-9 min-w-56 rounded-lg border border-input bg-background px-2 font-mono text-sm"
          >
            {branches.map((b) => (
              <option key={b.id} value={b.name}>
                {b.name}
                {b.is_deployment_branch ? ' (deployment)' : b.is_default ? ' (default)' : ''}
              </option>
            ))}
          </select>
        </div>
        <Button type="button" variant="outline" size="lg" onClick={sync} disabled={syncing}>
          <RefreshCw className={`size-4 ${syncing ? 'animate-spin' : ''}`} aria-hidden />
          {syncing ? 'Syncing…' : 'Sync from GitHub'}
        </Button>
        {canAdmin && branch !== deployment ? (
          <Button type="button" variant="ghost" size="lg" onClick={makeDeploymentBranch}>
            Make deployment branch
          </Button>
        ) : null}
      </div>

      <p role="status" aria-live="polite" className="text-sm text-success">
        {notice}
      </p>

      {failure ? <ErrorState failure={failure} /> : null}

      <fieldset className="space-y-2">
        <legend className="mb-2 text-sm font-medium">Commit</legend>
        {commits === null ? (
          <div role="status" className="space-y-2">
            <span className="sr-only">Loading commits…</span>
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : commits.length === 0 && !failure ? (
          <p className="text-sm text-muted-foreground">This branch has no commits.</p>
        ) : (
          <ul className="max-h-96 divide-y overflow-y-auto rounded-xl border">
            {commits.map((c, i) => {
              const id = `commit-${c.sha}`
              const checked = chosen?.sha === c.sha
              return (
                <li key={c.sha} className={checked ? 'bg-primary/5' : undefined}>
                  <label htmlFor={id} className="flex cursor-pointer items-start gap-3 p-3">
                    <input
                      id={id}
                      type="radio"
                      name="commit"
                      className="mt-1 accent-[var(--primary)]"
                      checked={checked}
                      onChange={() => {
                        setSha(c.sha)
                        setParams({ branch, sha: c.sha })
                      }}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm">{commitTitle(c.message)}</span>
                      <span className="block text-xs text-muted-foreground">
                        <span className="font-mono">{shortSha(c.sha)}</span> · {c.author_name ?? 'unknown author'} ·{' '}
                        {formatRelative(c.committed_at)}
                        {i === 0 ? ' · branch head' : ''}
                      </span>
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>
        )}
      </fieldset>

      <div className="flex flex-wrap items-center gap-3 border-t pt-4">
        <Button type="button" size="lg" onClick={analyze} disabled={!chosen || starting}>
          <Play className="size-4" aria-hidden />
          {starting ? 'Queuing…' : 'Analyze this commit'}
        </Button>
        {chosen ? (
          <p className="text-sm text-muted-foreground">
            <span className="font-mono">{shortSha(chosen.sha)}</span> on <span className="font-mono">{branch}</span>.
            The analysis runs in the background; you can follow every step live.
          </p>
        ) : null}
      </div>
    </div>
  )
}
