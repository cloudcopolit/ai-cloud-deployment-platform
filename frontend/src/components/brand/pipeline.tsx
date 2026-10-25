import { CapabilityBadge, type CapabilityLevel } from '@/components/app/states'
import { AGENTS } from '@/lib/agents'
import { cn } from '@/lib/utils'
import { SpriteIcon, TechLogo } from './icons'

type Step = {
  title: string
  caption: string
  level: CapabilityLevel
  visual: React.ReactNode
}

const avatar = (src: string) => (
  // eslint-disable-next-line @next/next/no-img-element -- small static SVG avatar
  <img src={src} alt="" className="size-11 rounded-xl" />
)

/* The product in one line of boxes. Levels match WORKLOG.md; update both together. */
const STEPS: Step[] = [
  {
    title: 'Your repository',
    caption: 'Connect by URL; pick a branch and commit',
    level: 'REAL',
    visual: <TechLogo name="github" label="" className="size-7" />
  },
  {
    title: AGENTS.ANALYSIS.name,
    caption: 'Services, ports, databases, risks',
    level: AGENTS.ANALYSIS.level,
    visual: avatar(AGENTS.ANALYSIS.avatar)
  },
  {
    title: AGENTS.ARCHITECTURE.name,
    caption: 'AWS design with reasons and cost',
    level: AGENTS.ARCHITECTURE.level,
    visual: avatar(AGENTS.ARCHITECTURE.avatar)
  },
  {
    title: 'You approve',
    caption: 'The exact Terraform plan, by hash',
    level: 'MISSING',
    visual: <SpriteIcon name="ui-user-check" className="size-7" />
  },
  {
    title: AGENTS.DEPLOYMENT.name,
    caption: 'Applies it, checks health',
    level: AGENTS.DEPLOYMENT.level,
    visual: avatar(AGENTS.DEPLOYMENT.avatar)
  },
  {
    title: 'Your AWS account',
    caption: 'Cross-account role, External ID',
    level: 'MISSING',
    visual: <TechLogo name="aws" label="" className="size-8" />
  }
]

/**
 * GitHub → agents → human approval → AWS. On a brand-navy panel, give the panel the `dark`
 * class so these tokens (and the badges) switch to their checked dark values.
 */
export function Pipeline({ showLevels = true, className }: { showLevels?: boolean; className?: string }) {
  return (
    <ol
      aria-label="How CloudPilot works"
      className={cn('grid gap-0 sm:grid-cols-3 lg:grid-cols-6', className)}
    >
      {STEPS.map((step, i) => (
        <li key={step.title} className="relative flex gap-3 pb-6 sm:flex-col sm:items-center sm:px-2 sm:text-center lg:pb-0">
          {i < STEPS.length - 1 ? (
            <>
              <span aria-hidden className="flow-y absolute left-[1.6rem] top-14 bottom-0 w-0.5 sm:hidden" />
              <span aria-hidden className="flow-x absolute left-[calc(50%+2.25rem)] right-[calc(-50%+2.25rem)] top-7 hidden h-0.5 lg:block" />
            </>
          ) : null}
          <span
            className="relative grid size-14 shrink-0 place-items-center rounded-2xl border bg-card text-foreground shadow-sm"
          >
            {step.visual}
          </span>
          <span className="min-w-0 space-y-1 pt-1">
            <span className="block text-sm font-semibold">{step.title}</span>
            <span className="block text-xs text-muted-foreground">{step.caption}</span>
            {showLevels ? <CapabilityBadge level={step.level} /> : null}
          </span>
        </li>
      ))}
    </ol>
  )
}
