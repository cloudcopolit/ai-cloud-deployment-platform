import Link from 'next/link'
import { ArrowRight } from 'lucide-react'

import { AgentCard } from '@/components/agents/agent-avatar'
import { CapabilityBadge, type CapabilityLevel } from '@/components/app/states'
import { ThemeToggle } from '@/components/app/theme'
import { SpriteIcon, TechLogo } from '@/components/brand/icons'
import { Logo } from '@/components/brand/logo'
import { Pipeline } from '@/components/brand/pipeline'
import { AGENT_ORDER, AGENTS } from '@/lib/agents'
import { AWS_ICONS } from '@/lib/aws-icons/manifest'

export const metadata = { title: { absolute: 'CloudPilot · From GitHub repository to AWS architecture' } }

const STACK = [
  ['python', 'Python'],
  ['fastapi', 'FastAPI'],
  ['nodedotjs', 'Node.js'],
  ['typescript', 'TypeScript'],
  ['react', 'React'],
  ['vite', 'Vite'],
  ['docker', 'Docker'],
  ['kubernetes', 'Kubernetes'],
  ['postgresql', 'PostgreSQL'],
  ['mysql', 'MySQL'],
  ['mongodb', 'MongoDB'],
  ['redis', 'Redis'],
  ['apachekafka', 'Kafka'],
  ['rabbitmq', 'RabbitMQ'],
  ['githubactions', 'GitHub Actions'],
  ['terraform', 'Terraform']
] as const

const SAFETY: { icon: `ui-${string}`; title: string; body: string; level: CapabilityLevel }[] = [
  {
    icon: 'ui-eye',
    title: 'Reads, never runs',
    body: 'Repository files are parsed as text. Code from your repository is never executed, and instructions written inside it are treated as data.',
    level: 'REAL'
  },
  {
    icon: 'ui-key',
    title: 'Secrets stay secret',
    body: 'A committed secret is reported by file and kind only. Values are never stored, logged or sent to a language model.',
    level: 'REAL'
  },
  {
    icon: 'ui-user-check',
    title: 'A person approves',
    body: 'An ADMIN or OWNER approves the exact Terraform plan. If the plan changes, the approval no longer applies.',
    level: 'MISSING'
  },
  {
    icon: 'ui-lock',
    title: 'Your account, short-lived access',
    body: 'A cross-account role with a per-team External ID, assumed through STS. No long-lived AWS keys are stored.',
    level: 'MISSING'
  }
]

/* Kept in step with WORKLOG.md §0 and HANDOFF.md. */
const STATUS: { area: string; level: CapabilityLevel; note: string }[] = [
  { area: 'GitHub repositories (public by URL)', level: 'REAL', note: 'Branches and commits from GitHub' },
  { area: 'Background jobs and live agent activity', level: 'REAL', note: 'Queue, heartbeats, cancel, time-outs' },
  { area: 'Repository analysis', level: 'REAL', note: 'Deterministic detectors, measured on 15 public repositories' },
  { area: 'Language-model assistance', level: 'MOCKED-ONLY', note: 'Until a provider API key is configured' },
  { area: 'Architecture proposals and cost', level: 'SIMULATED', note: 'Template prototype; real agent in progress' },
  { area: 'AWS account connection', level: 'MISSING', note: 'Designed' },
  { area: 'Terraform plan, approval and deployment', level: 'MISSING', note: 'Designed' }
]

export default function LandingPage() {
  return (
    <div className="min-h-svh bg-background">
      <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6">
          <Link href="/" aria-label="CloudPilot home">
            <Logo className="h-7" priority />
          </Link>
          <nav aria-label="Sections" className="hidden items-center gap-5 text-sm text-muted-foreground md:flex">
            <a href="#how" className="hover:text-foreground">
              How it works
            </a>
            <a href="#agents" className="hover:text-foreground">
              Agents
            </a>
            <a href="#safety" className="hover:text-foreground">
              Safety
            </a>
            <a href="#status" className="hover:text-foreground">
              Status
            </a>
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <ThemeToggle />
            <Link
              href="/login"
              className="inline-flex h-9 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Sign in
            </Link>
          </div>
        </div>
      </header>

      <main id="main">
        {/* Hero: always on the brand navy; `dark` switches the tokens inside to their dark values. */}
        <section className="dark relative overflow-hidden bg-brand-black text-foreground">
          <div aria-hidden className="bg-grid absolute inset-0 opacity-40" />
          <div
            aria-hidden
            className="absolute -left-40 -top-40 size-[36rem] rounded-full bg-brand-blue/30 blur-3xl"
          />
          <div aria-hidden className="absolute -bottom-48 right-0 size-[30rem] rounded-full bg-brand-teal/20 blur-3xl" />
          <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-4 py-20 sm:px-6 lg:grid-cols-[1.1fr_1fr] lg:py-28">
            <div className="space-y-7">
              <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-muted-foreground">
                <SpriteIcon name="ui-sparkles" className="size-3.5 text-brand-teal" />
                AI agents that show their work
              </p>
              <h1 className="font-display text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl lg:text-6xl">
                From GitHub repository to <span className="text-brand-gradient">a reviewed AWS architecture</span>.
              </h1>
              <p className="max-w-xl text-lg text-muted-foreground">
                CloudPilot reads your code, explains what it found, and has an Architect agent propose an AWS design
                with reasons, risks and cost. You decide what reaches your account.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link
                  href="/login"
                  className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-5 font-medium text-primary-foreground hover:bg-primary/90"
                >
                  <TechLogo name="github" label="" className="size-5" />
                  Continue with GitHub
                </Link>
                <a
                  href="#how"
                  className="inline-flex h-11 items-center gap-2 rounded-xl border border-white/20 px-5 font-medium hover:bg-white/5"
                >
                  See how it works <ArrowRight className="size-4" aria-hidden />
                </a>
              </div>
            </div>
            <HeroPreview />
          </div>
        </section>

        <section id="how" className="scroll-mt-20 border-b">
          <div className="mx-auto max-w-7xl space-y-10 px-4 py-20 sm:px-6">
            <SectionTitle
              eyebrow="How it works"
              title="One repository in, one reviewed plan out"
              body="Each step is a page you can come back to. Agents analyze and propose; deterministic code deploys, only after a person approves."
            />
            <Pipeline />
          </div>
        </section>

        <section id="agents" className="scroll-mt-20 border-b bg-muted/30">
          <div className="mx-auto max-w-7xl space-y-10 px-4 py-20 sm:px-6">
            <SectionTitle
              eyebrow="The crew"
              title="Meet the agents"
              body="Every agent has one job, strict inputs and outputs, and things it is never allowed to do. You can watch each one work, live."
            />
            <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {AGENT_ORDER.map((key) => (
                <li key={key} className="rounded-2xl border bg-card p-5 shadow-sm">
                  <AgentCard agent={AGENTS[key]} />
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="border-b">
          <div className="mx-auto max-w-7xl space-y-8 px-4 py-16 sm:px-6">
            <SectionTitle
              eyebrow="Detection"
              title="Understands the stack you already have"
              body="Languages, frameworks, Dockerfiles, Compose files, Kubernetes manifests, databases, caches and queues, including monorepos."
            />
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
              {STACK.map(([name, label]) => (
                <li key={name} className="flex flex-col items-center gap-2 rounded-xl border bg-card p-4 text-center">
                  <TechLogo name={name} label="" className="size-8" />
                  <span className="text-xs font-medium">{label}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="safety" className="scroll-mt-20 border-b bg-muted/30">
          <div className="mx-auto max-w-7xl space-y-10 px-4 py-20 sm:px-6">
            <SectionTitle
              eyebrow="Safety by design"
              title="AI proposes. People approve. Code applies."
              body="Language models never authorize, trigger or execute infrastructure changes."
            />
            <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {SAFETY.map((s) => (
                <li key={s.title} className="space-y-3 rounded-2xl border bg-card p-5">
                  <span className="bg-brand-gradient grid size-10 place-items-center rounded-xl text-white">
                    <SpriteIcon name={s.icon} className="size-5" />
                  </span>
                  <p className="font-semibold">{s.title}</p>
                  <p className="text-sm text-muted-foreground">{s.body}</p>
                  <CapabilityBadge level={s.level} />
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="status" className="scroll-mt-20">
          <div className="mx-auto max-w-4xl space-y-8 px-4 py-20 sm:px-6">
            <SectionTitle
              eyebrow="Platform status"
              title="What works today, stated plainly"
              body="REAL runs against the real service. SIMULATED runs against a stand-in. MOCKED-ONLY has no real backend configured. NOT BUILT is designed but not built."
            />
            <div className="overflow-hidden rounded-2xl border">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Capability status of this CloudPilot build</caption>
                <thead className="bg-muted/50 text-xs text-muted-foreground">
                  <tr>
                    <th scope="col" className="px-4 py-2.5 font-medium">
                      Capability
                    </th>
                    <th scope="col" className="px-4 py-2.5 font-medium">
                      Status
                    </th>
                    <th scope="col" className="hidden px-4 py-2.5 font-medium sm:table-cell">
                      Notes
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {STATUS.map((row) => (
                    <tr key={row.area}>
                      <td className="px-4 py-3 font-medium">{row.area}</td>
                      <td className="px-4 py-3">
                        <CapabilityBadge level={row.level} />
                      </td>
                      <td className="hidden px-4 py-3 text-muted-foreground sm:table-cell">{row.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="dark relative overflow-hidden bg-brand-black text-foreground">
          <div aria-hidden className="absolute -right-32 -top-32 size-96 rounded-full bg-brand-blue/30 blur-3xl" />
          <div className="relative mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-6 px-4 py-14 sm:px-6">
            <div className="space-y-2">
              <p className="font-display text-2xl font-semibold">Point CloudPilot at a repository.</p>
              <p className="text-muted-foreground">Sign in with GitHub, create a project and paste a repository URL.</p>
            </div>
            <Link
              href="/login"
              className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-5 font-medium text-primary-foreground hover:bg-primary/90"
            >
              Get started <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm text-muted-foreground sm:px-6">
          <Logo className="h-6" />
          <p>
            AWS service icons are the official AWS Architecture Icons. Technology logos belong to their owners.
          </p>
        </div>
      </footer>
    </div>
  )
}

function SectionTitle({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <div className="max-w-2xl space-y-3">
      <p className="text-sm font-semibold uppercase tracking-wider text-accent-strong">{eyebrow}</p>
      <h2 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h2>
      <p className="text-muted-foreground">{body}</p>
    </div>
  )
}

/** A labelled example of what a proposal looks like; no metrics, no numbers. */
function HeroPreview() {
  const chain = [
    { src: AWS_ICONS.users.src, label: 'Users' },
    { src: AWS_ICONS.alb.src, label: 'Load balancer' },
    { src: AWS_ICONS.ecs_service.src, label: 'ECS Fargate' },
    { src: AWS_ICONS.rds.src, label: 'RDS' }
  ]
  return (
    <figure className="relative rounded-3xl border border-white/10 bg-card/80 p-5 shadow-2xl backdrop-blur">
      <div className="flex items-center gap-3 border-b pb-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={AGENTS.ARCHITECTURE.avatar} alt="" className="size-10 rounded-xl" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">Architect agent</p>
          <p className="text-xs text-muted-foreground">Proposal for a web API with PostgreSQL</p>
        </div>
        <span className="rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground">Example</span>
      </div>
      <div className="flex items-center justify-between gap-1 py-6">
        {chain.map((n, i) => (
          <div key={n.label} className="flex flex-1 items-center gap-1">
            <div className="flex flex-col items-center gap-1.5">
              <span className="grid size-12 place-items-center rounded-xl bg-icon-surface shadow-sm sm:size-14">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={n.src} alt="" className="size-8 sm:size-10" />
              </span>
              <span className="text-[11px] text-muted-foreground">{n.label}</span>
            </div>
            {i < chain.length - 1 ? <span aria-hidden className="flow-x mb-5 h-0.5 flex-1" /> : null}
          </div>
        ))}
      </div>
      <ul className="space-y-2 border-t pt-4 text-sm">
        {[
          [AGENTS.ANALYSIS.avatar, 'Analysis agent', 'Found the services, ports and the database'],
          [AGENTS.ARCHITECTURE.avatar, 'Architect agent', 'Explained each component and its cost'],
          [AGENTS.DEPLOYMENT.avatar, 'Deployment engine', 'Waits for your approval']
        ].map(([src, who, what]) => (
          <li key={who} className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={src} alt="" className="size-7 rounded-lg" />
            <span className="font-medium">{who}</span>
            <span className="truncate text-muted-foreground">{what}</span>
          </li>
        ))}
      </ul>
      <figcaption className="sr-only">
        Example: users reach a load balancer, which sends traffic to containers on ECS Fargate that use an RDS
        database.
      </figcaption>
    </figure>
  )
}
