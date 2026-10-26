'use client'

import { useRouter } from 'next/navigation'
import { useId, useState } from 'react'
import { Crosshair } from 'lucide-react'

import { ErrorState } from '@/components/app/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { apiFetch } from '@/lib/api/client'
import type { ApiFailure } from '@/lib/api/result'
import { DeploymentSchema, EgressIpSchema, type AwsAccount } from '@/lib/api/schemas'

const DIGEST = /@sha256:[0-9a-f]{64}$/

export function DeployForm({
  projectId,
  versionId,
  accounts
}: {
  projectId: string
  versionId: string
  accounts: AwsAccount[]
}) {
  const router = useRouter()
  const id = useId()
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? '')
  const [image, setImage] = useState('')
  const [cidr, setCidr] = useState('')
  const [busy, setBusy] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [failure, setFailure] = useState<ApiFailure | null>(null)
  const imageOk = DIGEST.test(image.trim())

  async function detectIp() {
    setDetecting(true)
    const res = await apiFetch('/network/egress-ip', EgressIpSchema)
    setDetecting(false)
    if (res.ok) setCidr(res.data.cidr)
    else setFailure(res)
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setFailure(null)
    const res = await apiFetch(`/projects/${projectId}/deployments`, DeploymentSchema, {
      method: 'POST',
      body: {
        architecture_version_id: versionId,
        aws_account_id: accountId,
        image_uri: image.trim(),
        ingress_cidrs: cidr
          .split(',')
          .map((c) => c.trim())
          .filter(Boolean)
      }
    })
    if (!res.ok) {
      setBusy(false)
      return setFailure(res)
    }
    router.push(`/projects/${projectId}/deployments/${res.data.id}`)
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor={`${id}-account`}>AWS account</Label>
        <select
          id={`${id}-account`}
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
        >
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.aws_account_id} · {a.default_region} · verified
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${id}-image`}>Container image, pinned by digest</Label>
        <Input
          id={`${id}-image`}
          required
          placeholder="123456789012.dkr.ecr.us-east-1.amazonaws.com/app@sha256:…"
          value={image}
          onChange={(e) => setImage(e.target.value)}
          aria-describedby={`${id}-image-help`}
          className="font-mono text-xs"
        />
        <p id={`${id}-image-help`} className={`text-xs ${image && !imageOk ? 'text-destructive' : 'text-muted-foreground'}`}>
          Built by your own CI from the repository&apos;s Dockerfile. CloudPilot never builds images from analyzed code; a
          digest (not a tag) makes the deployment exactly reproducible.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${id}-cidr`}>Who may reach the load balancer</Label>
        <div className="flex gap-2">
          <Input
            id={`${id}-cidr`}
            required
            placeholder="203.0.113.7/32"
            value={cidr}
            onChange={(e) => setCidr(e.target.value)}
            className="font-mono text-xs"
          />
          <Button type="button" variant="outline" onClick={detectIp} disabled={detecting}>
            <Crosshair className="size-4" aria-hidden />
            {detecting ? 'Detecting…' : 'Use my IP'}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          IPv4 CIDRs, comma-separated, no wider than /16. The whole internet (0.0.0.0/0) is refused.
        </p>
      </div>

      {failure ? <ErrorState failure={failure} /> : null}

      <Button type="submit" size="lg" disabled={busy || !imageOk || !cidr || !accountId}>
        {busy ? 'Queuing the plan…' : 'Create the OpenTofu plan'}
      </Button>
    </form>
  )
}
