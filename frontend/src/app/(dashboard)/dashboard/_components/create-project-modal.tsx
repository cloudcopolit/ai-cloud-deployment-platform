'use client'

import React, { useState } from 'react'
import { Plus, Loader2 } from 'lucide-react'
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
import type { Project, Team } from '@/lib/validations/project'

interface CreateProjectModalProps {
  teams: Team[]
  onProjectCreated?: (project: Project) => void
  trigger?: React.ReactNode
}

export function CreateProjectModal({
  teams,
  onProjectCreated,
  trigger
}: CreateProjectModalProps) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedTeamId, setSelectedTeamId] = useState(teams[0]?.id ?? '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Project name is required')
      return
    }

    const teamId = selectedTeamId || teams[0]?.id
    if (!teamId) {
      setError('No team available to assign this project.')
      return
    }

    try {
      setLoading(true)
      setError(null)
      const res = await api.post(`/teams/${teamId}/projects`, {
        name: name.trim(),
        description: description.trim() || null
      })
      setName('')
      setDescription('')
      setOpen(false)
      onProjectCreated?.(res.data)
    } catch (err: any) {
      const msg =
        err.response?.data?.error?.message ??
        err.response?.data?.detail ??
        'Failed to create project.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button size="sm" className="gap-1.5 shadow-sm">
            <Plus className="size-4" />
            <span>New Project</span>
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create New Project</DialogTitle>
            <DialogDescription>
              A project organizes repositories, cloud architectures, and AWS deployments.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {error && (
              <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-xs text-destructive">
                {error}
              </div>
            )}

            {teams.length > 1 && (
              <div className="space-y-1.5">
                <Label htmlFor="team-select" className="text-xs">
                  Team
                </Label>
                <select
                  id="team-select"
                  value={selectedTeamId}
                  onChange={(e) => setSelectedTeamId(e.target.value)}
                  className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  {teams.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.role})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="project-name" className="text-xs">
                Project Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="project-name"
                placeholder="e.g. Acme Online Store"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={loading}
                autoFocus
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="project-desc" className="text-xs">
                Description (Optional)
              </Label>
              <Input
                id="project-desc"
                placeholder="Brief description of this application stack"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={loading}
              />
            </div>
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
              <span>Create Project</span>
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
