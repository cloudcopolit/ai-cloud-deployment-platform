'use client'

import React from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  FolderGit2,
  GitBranch,
  Cpu,
  Rocket,
  Cloud,
  ChevronRight,
  ShieldCheck,
  CheckCircle2,
  Sparkles
} from 'lucide-react'

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { LogoutButton } from './logout-button'
import type { User } from '@/lib/validations/auth'
import type { Team } from '@/lib/validations/project'
import logoIcon from '/public/logos/logo-icon.svg'

interface DashboardSidebarProps {
  user: User
  teams: Team[]
  activeTeamId?: string
}

export function DashboardSidebar({ user, teams, activeTeamId }: DashboardSidebarProps) {
  const pathname = usePathname()

  const currentTeam =
    teams.find((t) => t.id === activeTeamId) ?? teams[0] ?? {
      name: `${user.name ?? user.github_user_id}'s Team`,
      role: 'OWNER',
      plan_code: 'FREE'
    }

  const initials = (user.name ?? user.github_user_id)
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  const navItems = [
    {
      title: 'Overview',
      href: '/dashboard',
      icon: LayoutDashboard,
      active: pathname === '/dashboard'
    },
    {
      title: 'Projects',
      href: '/dashboard#projects',
      icon: FolderGit2,
      count: currentTeam.project_count
    },
    {
      title: 'Repositories',
      href: '/dashboard#repositories',
      icon: GitBranch
    },
    {
      title: 'Architecture & AI',
      href: '/dashboard#analysis',
      icon: Cpu,
      badge: 'AI'
    },
    {
      title: 'Deployments',
      href: '/dashboard#deployments',
      icon: Rocket
    },
    {
      title: 'AWS Accounts',
      href: '/dashboard#aws',
      icon: Cloud
    }
  ]

  return (
    <aside className="w-64 shrink-0 border-r border-border/70 bg-card/50 backdrop-blur-sm flex flex-col justify-between min-h-svh">
      {/* Top Header / Brand */}
      <div className="p-4 space-y-4">
        <Link href="/dashboard" className="flex items-center gap-3 px-2 py-1.5 group">
          <div className="relative size-9 rounded-xl bg-gradient-to-br from-[#2F6BFF] to-[#19D3C5] p-0.5 shadow-md shadow-[#2F6BFF]/20 group-hover:scale-105 transition-transform">
            <div className="size-full bg-card rounded-[10px] flex items-center justify-center p-1.5">
              <Image src={logoIcon} alt="CloudPilot Logo" className="size-full" />
            </div>
          </div>
          <div className="flex flex-col">
            <span className="font-bold tracking-tight text-base leading-none text-foreground flex items-center gap-1">
              Cloud<span className="text-[#19D3C5]">Pilot</span>
            </span>
            <span className="text-[10px] text-muted-foreground font-mono tracking-wider mt-0.5">
              AWS PLATFORM
            </span>
          </div>
        </Link>

        {/* Team Selector / Info Pill */}
        <div className="rounded-lg border border-border/60 bg-muted/30 p-2.5 flex items-center justify-between">
          <div className="space-y-0.5 truncate">
            <div className="text-xs font-semibold truncate text-foreground">
              {currentTeam.name}
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <Badge variant="outline" className="text-[9px] px-1 py-0 h-4 uppercase font-semibold">
                {currentTeam.role}
              </Badge>
              <span>•</span>
              <span className="text-[#19D3C5] font-medium">{currentTeam.plan_code} PLAN</span>
            </div>
          </div>
          <ShieldCheck className="size-4 text-muted-foreground/70 shrink-0" />
        </div>

        {/* Navigation Items */}
        <nav className="space-y-1 pt-1" aria-label="Main Navigation">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = item.active ?? false

            return (
              <Link
                key={item.title}
                href={item.href}
                className={`flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary/10 text-primary font-semibold'
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className={`size-4 ${isActive ? 'text-primary' : 'text-muted-foreground'}`} />
                  <span>{item.title}</span>
                </div>
                <div className="flex items-center gap-1">
                  {item.badge && (
                    <Badge variant="brand" className="text-[10px] px-1.5 py-0 h-4">
                      {item.badge}
                    </Badge>
                  )}
                  {typeof item.count === 'number' && item.count > 0 && (
                    <span className="text-xs text-muted-foreground px-1.5 py-0.5 rounded-full bg-muted">
                      {item.count}
                    </span>
                  )}
                </div>
              </Link>
            )
          })}
        </nav>
      </div>

      {/* Bottom Area: Engine status & User profile */}
      <div className="p-4 border-t border-border/70 space-y-3">
        {/* System Health Indicator */}
        <div className="flex items-center justify-between rounded-md bg-muted/40 px-2.5 py-1.5 text-[11px] text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <div className="size-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>AI Orchestrator</span>
          </div>
          <span className="font-mono text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">
            READY
          </span>
        </div>

        {/* User Profile */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center gap-2.5 min-w-0">
            <Avatar className="size-8 border border-border">
              <AvatarImage src={user.avatar_url ?? undefined} alt={user.name ?? user.github_user_id} />
              <AvatarFallback className="text-xs font-semibold">{initials}</AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <div className="text-xs font-medium truncate text-foreground">
                {user.name ?? user.github_user_id}
              </div>
              <div className="text-[10px] text-muted-foreground truncate">
                @{user.github_user_id}
              </div>
            </div>
          </div>
          <LogoutButton />
        </div>
      </div>
    </aside>
  )
}
