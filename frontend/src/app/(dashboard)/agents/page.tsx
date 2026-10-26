import { Suspense } from 'react'

import { AgentCard } from '@/components/agents/agent-avatar'
import { PageHeader } from '@/components/app/page-header'
import { CapabilityBadge, ErrorState } from '@/components/app/states'
import { Pipeline } from '@/components/brand/pipeline'
import { Skeleton } from '@/components/ui/skeleton'
import { AGENT_ORDER, AGENTS } from '@/lib/agents'
import { apiGet } from '@/lib/api/server'
import { LlmProviderSchema } from '@/lib/api/schemas'

export const metadata = { title: 'Agents' }

const PROVIDER_NAMES: Record<string, string> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  gemini: 'Google Gemini',
  xai: 'xAI'
}

export default function AgentsPage() {
  return (
    <>
      <PageHeader
        title="Agents"
        description="Who does what in CloudPilot, what each one is never allowed to do, and how real it is in this build."
      />

      <section aria-labelledby="flow" className="space-y-4 rounded-2xl border bg-card p-5">
        <h2 id="flow" className="font-semibold">
          How the work flows
        </h2>
        <Pipeline />
      </section>

      <section aria-labelledby="crew" className="space-y-3">
        <h2 id="crew" className="font-semibold">
          The crew
        </h2>
        <ul className="grid gap-4 md:grid-cols-2">
          {AGENT_ORDER.map((key) => (
            <li key={key} className="rounded-2xl border bg-card p-5">
              <AgentCard agent={AGENTS[key]} />
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="models" className="space-y-3">
        <div>
          <h2 id="models" className="font-semibold">
            Language-model providers
          </h2>
          <p className="text-sm text-muted-foreground">
            Tried in priority order when an agent needs a model. Read from this deployment&apos;s configuration; API
            keys are never shown.
          </p>
        </div>
        <Suspense fallback={<Skeleton className="h-48 w-full rounded-2xl" />}>
          <Providers />
        </Suspense>
      </section>
    </>
  )
}

async function Providers() {
  const res = await apiGet('/llm/providers', LlmProviderSchema.array())
  if (!res.ok) return <ErrorState failure={res} />
  return (
    <div className="overflow-x-auto rounded-2xl border">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Language-model providers and their status</caption>
        <thead className="bg-muted/50 text-xs text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-2.5 font-medium">
              Priority
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              Provider
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              Status
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              Model chosen
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              Check
            </th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {res.data.map((p, i) => (
            <tr key={p.provider}>
              <td className="px-4 py-3 font-mono text-xs">{i + 1}</td>
              <td className="px-4 py-3 font-medium">{PROVIDER_NAMES[p.provider] ?? p.provider}</td>
              <td className="px-4 py-3">
                <CapabilityBadge level={p.mode} />
              </td>
              <td className="px-4 py-3 font-mono text-xs">{p.chosen_model ?? '—'}</td>
              <td className="px-4 py-3 text-xs text-muted-foreground">
                {!p.configured
                  ? 'No API key configured'
                  : p.reachable === null
                    ? 'Not checked yet'
                    : p.reachable
                      ? `Reachable · ${p.models_listed ?? '?'} models listed${p.latency_ms !== null ? ` · ${p.latency_ms} ms` : ''}`
                      : `Unreachable${p.error ? `: ${p.error}` : ''}`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
