'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { ArrowRight } from 'lucide-react'

import { AgentAvatar } from '@/components/agents/agent-avatar'
import { CapabilityBadge, ErrorState } from '@/components/app/states'
import { Button } from '@/components/ui/button'
import { AGENTS } from '@/lib/agents'
import { apiFetch } from '@/lib/api/client'
import type { ApiFailure } from '@/lib/api/result'
import { ArchitectureVersionSchema } from '@/lib/api/schemas'

/** After a successful analysis: hand the report to the Architect agent, or open its last proposal. */
export function ArchitectHandoff({
  analysisId,
  projectId,
  existingHref
}: {
  analysisId: string
  projectId: string
  existingHref: string | null
}) {
  const router = useRouter()
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState<ApiFailure | null>(null)

  async function propose() {
    setBusy(true)
    setFailure(null)
    const res = await apiFetch(`/analyses/${analysisId}/architectures`, ArchitectureVersionSchema, {
      method: 'POST',
      body: {}
    })
    if (!res.ok) {
      setBusy(false)
      return setFailure(res)
    }
    router.push(`/projects/${projectId}/architectures/${res.data.architecture_id}/versions/${res.data.version_number}`)
  }

  return (
    <section
      aria-labelledby="handoff"
      className="relative overflow-hidden rounded-2xl border border-primary/40 bg-card p-5"
    >
      <div aria-hidden className="bg-brand-gradient absolute inset-x-0 top-0 h-1" />
      <div className="flex flex-wrap items-center gap-4">
        <AgentAvatar agent={AGENTS.ARCHITECTURE} size="lg" working={busy} />
        <div className="min-w-0 flex-1 space-y-1">
          <h2 id="handoff" className="flex flex-wrap items-center gap-2 font-display text-lg font-semibold">
            Next: the Architect agent
            <CapabilityBadge level="SIMULATED" />
          </h2>
          <p className="text-sm text-muted-foreground">
            It turns this report into an AWS architecture with a diagram, reasons, risks and a monthly estimate. Nothing
            is created in AWS.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {existingHref ? (
            <Button asChild variant="outline">
              <Link href={existingHref}>Open latest proposal</Link>
            </Button>
          ) : null}
          <Button type="button" onClick={propose} disabled={busy}>
            {busy ? 'The Architect is working…' : existingHref ? 'Propose again' : 'Propose an architecture'}
            {busy ? null : <ArrowRight className="size-4" aria-hidden />}
          </Button>
        </div>
      </div>
      {failure ? (
        <div className="mt-4">
          <ErrorState failure={failure} />
        </div>
      ) : null}
    </section>
  )
}
