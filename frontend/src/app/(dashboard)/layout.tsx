import Link from 'next/link'
import { Suspense } from 'react'
import { redirect } from 'next/navigation'

import { ThemeToggle } from '@/components/app/theme'
import { Skeleton } from '@/components/ui/skeleton'
import { apiGet } from '@/lib/api/server'
import { GitHubAccessSchema, ProjectSchema, TeamSchema } from '@/lib/api/schemas'
import { getCurrentUser } from '@/lib/session'
import { DashboardSidebar } from './_components/dashboard-sidebar'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-svh bg-background text-foreground">
      <Suspense fallback={<SidebarSkeleton />}>
        <Sidebar />
      </Suspense>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-end gap-3 border-b bg-background/90 px-4 backdrop-blur sm:px-6">
          {/* the sidebar is hidden below md; the overview page lists every project */}
          <Link href="/dashboard" className="mr-auto font-semibold md:hidden">
            CloudPilot
          </Link>
          <Suspense fallback={<Skeleton className="h-6 w-48" />}>
            <GitHubStatus />
          </Suspense>
          <ThemeToggle />
        </header>
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 space-y-6 p-4 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  )
}

async function Sidebar() {
  const user = await getCurrentUser()
  if (!user) redirect('/login')
  // Both requests start together (no waterfall).
  const [teams, projects] = await Promise.all([
    apiGet('/teams', TeamSchema.array()),
    apiGet('/projects', ProjectSchema.array())
  ])
  return (
    <DashboardSidebar
      user={user}
      teams={teams.ok ? teams.data : []}
      projects={projects.ok ? projects.data : []}
    />
  )
}

/** Real GitHub reachability for this deployment; never a decorative "connected" light. */
async function GitHubStatus() {
  const access = await apiGet('/github/access', GitHubAccessSchema)
  if (!access.ok) {
    return (
      <span className="text-xs text-destructive">
        {access.kind === 'offline' ? 'API unreachable' : 'GitHub status unavailable'}
      </span>
    )
  }
  const a = access.data
  const mode = a.app_installations ? 'GitHub App' : a.token_configured ? 'token' : 'anonymous'
  const low = a.rate_limit_remaining !== null && a.rate_limit_remaining < 10
  return (
    <span
      className={`hidden items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-xs sm:inline-flex ${low ? 'border-warning/60 text-warning' : 'text-muted-foreground'}`}
      title="How this CloudPilot instance reads GitHub, and the API requests left this hour"
    >
      GitHub: {mode}
      {a.rate_limit_remaining !== null ? ` · ${a.rate_limit_remaining}/${a.rate_limit_limit} req left` : ''}
    </span>
  )
}

function SidebarSkeleton() {
  return (
    <aside className="hidden min-h-svh w-64 shrink-0 space-y-4 border-r p-4 md:block">
      <Skeleton className="h-8 w-36" />
      <Skeleton className="h-8 w-full" />
      <Skeleton className="h-8 w-full" />
    </aside>
  )
}
