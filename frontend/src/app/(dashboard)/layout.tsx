import { Suspense } from 'react'
import { redirect } from 'next/navigation'
import { getCurrentUser } from '@/lib/session'
import { LogoutButton } from './_components/logout-button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Skeleton } from '@/components/ui/skeleton'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-svh flex-col">
      {/* Static header — prerendered instantly */}
      <header className="flex h-14 items-center justify-between border-b px-6">
        <span className="text-sm font-semibold tracking-tight">
          Cloud<span className="font-normal text-muted-foreground">Pilot</span>
        </span>

        {/* Dynamic content — streams in after auth check */}
        <Suspense fallback={<DashboardSkeleton />}>
          <AuthenticatedContent />
        </Suspense>
      </header>
      <main className="flex-1 p-6">{children}</main>
    </div>
  )
}

async function AuthenticatedContent() {
  const user = await getCurrentUser()
  if (!user) redirect('/login')

  const initials = (user.name ?? user.github_user_id)
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <>
      <div className="flex h-14 items-center justify-end gap-3 border-b px-6">
        <Avatar className="size-8">
          <AvatarImage src={user.avatar_url ?? undefined} alt="" />
          <AvatarFallback>{initials}</AvatarFallback>
        </Avatar>
        <span className="text-sm text-muted-foreground">{user.name ?? user.github_user_id}</span>
        <LogoutButton />
      </div>
    </>
  )
}

function DashboardSkeleton() {
  return (
    <div className="flex-1 space-y-4 p-6">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-4 w-32" />
    </div>
  )
}
