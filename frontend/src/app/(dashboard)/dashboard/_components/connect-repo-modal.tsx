'use client'

import React, { useState } from 'react'
import { GitBranch, Loader2, Sparkles, Check, Globe } from 'lucide-react'
import { api } from '@/lib/axios-browser'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import type { AvailableRepository, Project, Repository } from '@/lib/validations/project'

interface ConnectRepoModalProps {
  projects: Project[]
  availableRepos: AvailableRepository[]
  preselectedProjectId?: string
  onRepoConnected?: (repo: Repository) => void
  trigger?: React.ReactNode
}

export function ConnectRepoModal({
  projects,
  availableRepos,
  preselectedProjectId,
  onRepoConnected,
  trigger
}: ConnectRepoModalProps) {
  const [open, setOpen] = useState(false)
  const [selectedProjectId, setSelectedProjectId] = useState(
    preselectedProjectId ?? projects[0]?.id ?? ''
  )
  const [mode, setMode] = useState<'template' | 'custom'>('template')
  const [selectedTemplateId, setSelectedTemplateId] = useState(
    availableRepos[0]?.id ?? ''
  )

  // Custom form fields
  const [owner, setOwner] = useState('')
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [defaultBranch, setDefaultBranch] = useState('main')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSelectTemplate = (template: AvailableRepository) => {
    setSelectedTemplateId(template.id)
    const [templateOwner, templateName] = template.full_name.split('/')
    setOwner(templateOwner || 'acme')
    setName(templateName || template.name)
    setUrl(template.url)
    setDefaultBranch(template.default_branch || 'main')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const projectId = selectedProjectId || projects[0]?.id
    if (!projectId) {
      setError('Please select a project first.')
      return
    }

    let repoData: {
      github_repository_id: string
      owner: string
      name: string
      url: string
      default_branch: string
    }

    if (mode === 'template') {
      const template = availableRepos.find((t) => t.id === selectedTemplateId) ?? availableRepos[0]
      if (!template) {
        setError('Please select a reference repository.')
        return
      }
      const parts = template.full_name.split('/')
      repoData = {
        github_repository_id: template.id,
        owner: parts[0] || 'acme',
        name: parts[1] || template.name,
        url: template.url,
        default_branch: template.default_branch || 'main'
      }
    } else {
      if (!owner.trim() || !name.trim() || !url.trim()) {
        setError('Owner, repository name, and URL are required.')
        return
      }
      repoData = {
        github_repository_id: `gh_${Date.now()}`,
        owner: owner.trim(),
        name: name.trim(),
        url: url.trim(),
        default_branch: defaultBranch.trim() || 'main'
      }
    }

    try {
      setLoading(true)
      setError(null)
      const res = await api.post(`/projects/${projectId}/repositories`, repoData)
      setOpen(false)
      onRepoConnected?.(res.data)
    } catch (err: any) {
      const msg =
        err.response?.data?.error?.message ??
        err.response?.data?.detail ??
        'Failed to connect repository.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="outline" size="sm" className="gap-1.5 shadow-sm">
            <GitBranch className="size-4" />
            <span>Connect Repository</span>
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Connect GitHub Repository</DialogTitle>
            <DialogDescription>
              Attach a source code repository to analyze dependencies, generate cloud architectures, and deploy.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {error && (
              <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-xs text-destructive">
                {error}
              </div>
            )}

            {/* Project Selection */}
            {projects.length > 1 && (
              <div className="space-y-1.5">
                <Label htmlFor="proj-select" className="text-xs">
                  Target Project
                </Label>
                <select
                  id="proj-select"
                  value={selectedProjectId}
                  onChange={(e) => setSelectedProjectId(e.target.value)}
                  className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.team_name ?? 'Personal'})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Mode Toggle Tabs */}
            <div className="grid grid-cols-2 p-1 bg-muted rounded-lg text-xs font-medium">
              <button
                type="button"
                onClick={() => setMode('template')}
                className={`py-1.5 rounded-md transition-all flex items-center justify-center gap-1.5 ${
                  mode === 'template' ? 'bg-background shadow-xs text-foreground font-semibold' : 'text-muted-foreground'
                }`}
              >
                <Sparkles className="size-3.5 text-[#19D3C5]" />
                <span>Reference Applications</span>
              </button>
              <button
                type="button"
                onClick={() => setMode('custom')}
                className={`py-1.5 rounded-md transition-all flex items-center justify-center gap-1.5 ${
                  mode === 'custom' ? 'bg-background shadow-xs text-foreground font-semibold' : 'text-muted-foreground'
                }`}
              >
                <Globe className="size-3.5 text-primary" />
                <span>Custom Repository</span>
              </button>
            </div>

            {/* Reference Apps Mode */}
            {mode === 'template' && (
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">
                  Select a verified stack to run an end-to-end cloud deployment:
                </Label>
                <div className="grid gap-2 max-h-56 overflow-y-auto pr-1">
                  {availableRepos.map((tpl) => {
                    const isSelected = selectedTemplateId === tpl.id
                    return (
                      <div
                        key={tpl.id}
                        onClick={() => handleSelectTemplate(tpl)}
                        className={`p-3 rounded-lg border text-left cursor-pointer transition-all ${
                          isSelected
                            ? 'border-primary bg-primary/5 shadow-xs'
                            : 'border-border/70 hover:border-border hover:bg-muted/30'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="font-semibold text-xs text-foreground flex items-center gap-1.5">
                            <span>{tpl.name}</span>
                            {tpl.language && (
                              <Badge variant="outline" className="text-[10px] font-mono py-0 h-4">
                                {tpl.language}
                              </Badge>
                            )}
                          </div>
                          {isSelected && <Check className="size-4 text-primary" />}
                        </div>
                        <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                          {tpl.description}
                        </p>
                        <div className="mt-1.5 text-[10px] text-muted-foreground/80 font-mono">
                          branch: {tpl.default_branch}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Custom Mode */}
            {mode === 'custom' && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="repo-owner" className="text-xs">
                      Owner/Org <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      id="repo-owner"
                      placeholder="e.g. acme-corp"
                      value={owner}
                      onChange={(e) => setOwner(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="repo-name" className="text-xs">
                      Repository <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      id="repo-name"
                      placeholder="e.g. payment-service"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="repo-url" className="text-xs">
                    Clone URL <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="repo-url"
                    placeholder="https://github.com/acme-corp/payment-service"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="repo-branch" className="text-xs">
                    Deployment Branch
                  </Label>
                  <Input
                    id="repo-branch"
                    placeholder="main"
                    value={defaultBranch}
                    onChange={(e) => setDefaultBranch(e.target.value)}
                  />
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={loading} className="gap-1.5">
              {loading && <Loader2 className="size-3.5 animate-spin" />}
              <span>Connect Repository</span>
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
