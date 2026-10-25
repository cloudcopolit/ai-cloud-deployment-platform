import React, { Suspense } from 'react'
import { redirect } from 'next/navigation'
import { getCurrentUser } from '@/lib/session'
import { apiServer } from '@/lib/axios-server'
import { DashboardSidebar } from './_components/dashboard-sidebar'
import type { Team } from '@/lib/validations/project'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-svh bg-background text-foreground">
      {/* Streamed sidebar with user & teams */}
      <Suspense fallback={<SidebarSkeleton />}>
        <AsyncSidebarWrapper />
      </Suspense>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* Top Navbar — static shell */}
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-border/70 bg-background/80 backdrop-blur-md px-6">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-semibold text-foreground">CloudPilot</span>
            <span className="text-muted-foreground">/</span>
            <span className="text-muted-foreground">Workspace</span>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2">
              <span className="relative flex size-2">
                <span className="animate-ping absolute inline-flex size-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full size-2 bg-emerald-500" />
              </span>
              <span className="text-xs font-mono text-muted-foreground">AWS us-east-1 (Connected)</span>
            </div>
            <Badge variant="outline" className="text-[11px] font-mono font-medium">
              MVP-v1.0
            </Badge>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-6 lg:p-8 max-w-7xl w-full mx-auto">{children}</main>
      </div>
    </div>
  )
}

async function AsyncSidebarWrapper() {
  const user = await getCurrentUser()
  if (!user) {
    redirect('/login')
  }

  let teams: Team[] = []
  try {
    const api = await apiServer()
    const res = await api.get('/teams')
    teams = res.data
  } catch {
    teams = []
  }

  return <DashboardSidebar user={user} teams={teams} />
}

function SidebarSkeleton() {
  return (
    <aside className="w-64 shrink-0 border-r border-border/70 bg-card/50 p-4 space-y-6 min-h-svh hidden md:flex md:flex-col justify-between">
      <div className="space-y-4">
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-12 w-full rounded-lg" />
        <div className="space-y-2 pt-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      </div>
      <Skeleton className="h-12 w-full rounded-lg" />
    </aside>
  )
}
