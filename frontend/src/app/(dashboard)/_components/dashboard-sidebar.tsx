'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

import { SpriteIcon } from '@/components/brand/icons'
import { Logo } from '@/components/brand/logo'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import type { Project, Team } from '@/lib/api/schemas'
import type { User } from '@/lib/validations/auth'
import { LogoutButton } from './logout-button'

interface DashboardSidebarProps {
  user: User
  teams: Team[]
  projects: Project[]
}

export function DashboardSidebar({ user, teams, projects }: DashboardSidebarProps) {
  const pathname = usePathname()
  const display = user.name ?? user.github_user_id
  const initials = display
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  const link = (href: string, active: boolean) =>
    `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm ${
      active
        ? 'bg-primary/10 font-medium text-primary shadow-[inset_2px_0_0_var(--primary)]'
        : 'text-muted-foreground hover:bg-muted hover:text-foreground'
    }`

  return (
    <aside className="hidden min-h-svh w-64 shrink-0 flex-col justify-between border-r bg-sidebar md:flex">
      <div className="space-y-6 p-4">
        <Link href="/dashboard" className="block px-2 py-1" aria-label="CloudPilot overview">
          <Logo className="h-7" />
        </Link>

        <nav aria-label="Main" className="space-y-5">
          <div className="space-y-1">
          <Link
            href="/dashboard"
            className={link('/dashboard', pathname === '/dashboard')}
            aria-current={pathname === '/dashboard' ? 'page' : undefined}
          >
            <SpriteIcon name="ui-home" className="size-4" />
            Overview
          </Link>
          <Link
            href="/agents"
            className={link('/agents', pathname === '/agents')}
            aria-current={pathname === '/agents' ? 'page' : undefined}
          >
            <SpriteIcon name="ui-bot" className="size-4" />
            Agents
          </Link>
          <Link
            href="/aws"
            className={link('/aws', pathname === '/aws')}
            aria-current={pathname === '/aws' ? 'page' : undefined}
          >
            <SpriteIcon name="ui-cloud" className="size-4" />
            AWS accounts
          </Link>
          </div>

          {teams.map((team) => {
            const teamProjects = projects.filter((p) => p.team_id === team.id)
            return (
              <div key={team.id} className="space-y-1">
                <p className="flex items-center justify-between px-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  <span className="truncate">{team.name}</span>
                  <span className="font-mono normal-case">{team.role.toLowerCase()}</span>
                </p>
                {teamProjects.length === 0 ? (
                  <p className="px-3 py-1 text-xs text-muted-foreground">No projects</p>
                ) : (
                  teamProjects.map((project) => {
                    const href = `/projects/${project.id}`
                    const active = pathname.startsWith(href)
                    return (
                      <Link
                        key={project.id}
                        href={href}
                        className={link(href, active)}
                        aria-current={active ? 'page' : undefined}
                      >
                        <SpriteIcon name="ui-folder" className="size-4" />
                        <span className="truncate">{project.name}</span>
                      </Link>
                    )
                  })
                )}
              </div>
            )
          })}
        </nav>
      </div>

      <div className="flex items-center gap-3 border-t p-4">
        <Avatar className="size-8">
          {user.avatar_url ? <AvatarImage src={user.avatar_url} alt="" /> : null}
          <AvatarFallback>{initials}</AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{display}</p>
          {user.email ? <p className="truncate text-xs text-muted-foreground">{user.email}</p> : null}
        </div>
        <LogoutButton />
      </div>
    </aside>
  )
}
