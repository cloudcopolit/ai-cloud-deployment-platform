'use client'

import { Check, X } from 'lucide-react'

import { CapabilityBadge } from '@/components/app/states'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { AgentProfile } from '@/lib/agents'
import { cn } from '@/lib/utils'

const SIZES = { sm: 'size-8 rounded-lg', md: 'size-10 rounded-xl', lg: 'size-14 rounded-2xl' } as const

/** The agent's gradient avatar; a soft pulse while it is working. Decorative on its own. */
export function AgentPortrait({
  agent,
  size = 'md',
  working = false,
  className
}: {
  agent: AgentProfile
  size?: keyof typeof SIZES
  working?: boolean
  className?: string
}) {
  return (
    <span className={cn('relative inline-flex shrink-0', className)}>
      {working ? (
        <span aria-hidden className={cn('absolute inset-0 animate-ping bg-brand-teal/40', SIZES[size])} />
      ) : null}
      {/* eslint-disable-next-line @next/next/no-img-element -- tiny static SVG, no optimization needed */}
      <img src={agent.avatar} alt="" className={cn('relative shadow-sm', SIZES[size])} />
    </span>
  )
}

/** What an agent does and never does, with its honesty label. */
export function AgentCard({ agent, children }: { agent: AgentProfile; children?: React.ReactNode }) {
  return (
    <div className="space-y-3 text-sm">
      <div className="flex items-start gap-3">
        <AgentPortrait agent={agent} size="lg" />
        <div className="min-w-0 space-y-1">
          <p className="font-display text-base font-semibold leading-tight">{agent.name}</p>
          <p className="text-muted-foreground">{agent.tagline}</p>
          <div className="flex flex-wrap items-center gap-1.5">
            <CapabilityBadge level={agent.level} />
            <span className="text-xs text-muted-foreground">{agent.isAi ? 'AI agent' : 'Deterministic, no AI'}</span>
          </div>
        </div>
      </div>
      <ul className="space-y-1">
        {agent.does.map((d) => (
          <li key={d} className="flex gap-2">
            <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
            <span>{d}</span>
          </li>
        ))}
        {agent.never.map((d) => (
          <li key={d} className="flex gap-2 text-muted-foreground">
            <X className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
            <span>
              <span className="sr-only">Never: </span>
              {d}
            </span>
          </li>
        ))}
      </ul>
      <p className="rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">{agent.levelNote}</p>
      {children}
    </div>
  )
}

/**
 * An agent's avatar (and optionally its name) that opens a card about the agent. Keyboard and
 * touch friendly: it is a button with a popover, not a hover-only tooltip.
 */
export function AgentAvatar({
  agent,
  size = 'md',
  showName = false,
  working = false,
  details,
  className
}: {
  agent: AgentProfile
  size?: keyof typeof SIZES
  showName?: boolean
  working?: boolean
  /** Live facts for this run (status, model, tokens…), shown under the profile. */
  details?: React.ReactNode
  className?: string
}) {
  return (
    <Popover>
      <PopoverTrigger
        className={cn(
          'group inline-flex items-center gap-2.5 rounded-xl text-left outline-offset-4',
          showName && 'pr-1',
          className
        )}
        aria-label={`About the ${agent.name}`}
      >
        <AgentPortrait agent={agent} size={size} working={working} className="transition-transform group-hover:scale-105" />
        {showName ? (
          <span className="font-medium underline-offset-4 group-hover:underline">{agent.name}</span>
        ) : null}
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[22rem]">
        <AgentCard agent={agent}>{details}</AgentCard>
      </PopoverContent>
    </Popover>
  )
}
