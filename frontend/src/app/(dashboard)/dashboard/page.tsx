import React, { Suspense } from 'react'
import { redirect } from 'next/navigation'
import { getCurrentUser } from '@/lib/session'
import { apiServer } from '@/lib/axios-server'
import { DashboardClient } from './_components/dashboard-client'
import type { AvailableRepository, Project, Team } from '@/lib/validations/project'
import { Skeleton } from '@/components/ui/skeleton'

export const metadata = {
  title: 'Dashboard — CloudPilot'
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<DashboardLoadingSkeleton />}>
      <DashboardDataFetcher />
    </Suspense>
  )
}

async function DashboardDataFetcher() {
  const user = await getCurrentUser()
  if (!user) {
    redirect('/login')
  }

  let teams: Team[] = []
  let projects: Project[] = []
  let availableRepos: AvailableRepository[] = []

  try {
    const api = await apiServer()
    const [teamsRes, projectsRes, reposRes] = await Promise.allSettled([
      api.get('/teams'),
      api.get('/projects'),
      api.get('/repositories/available')
    ])

    if (teamsRes.status === 'fulfilled') {
      teams = teamsRes.value.data
    }
    if (projectsRes.status === 'fulfilled') {
      projects = projectsRes.value.data
    }
    if (reposRes.status === 'fulfilled') {
      availableRepos = reposRes.value.data
    }
  } catch {
    // Graceful fallback to empty state
  }

  return (
    <DashboardClient
      user={user}
      initialTeams={teams}
      initialProjects={projects}
      availableRepos={availableRepos}
    />
  )
}

function DashboardLoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="flex justify-between items-center pb-4 border-b">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-9 w-32" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
      <Skeleton className="h-64 w-full rounded-xl" />
    </div>
  )
}
