import { Layers, ShieldCheck } from 'lucide-react'
import githubIcon from '@/../public/icons/brands/github.svg'
import Image from 'next/image'
import { permissions } from '../constants'
import { Button } from '@/components/ui/button'
import Link from 'next/link'

export function ConnectCard() {
  return (
    <div className="mx-auto w-full max-w-204 rounded-2xl border bg-card p-10 shadow-sm sm:p-12">
      {/* Integration Flow Graphic */}
      <div className="mb-10 flex items-center justify-center gap-3">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#0A0523]">
          <Image
            src={githubIcon}
            alt="github icon"
            width={32}
            className="h-8 w-8 invert dark:invert"
          />
        </div>

        <div className="flex items-center gap-1">
          <div className="h-2 w-2 rounded-full bg-muted-foreground" />
          <div className="h-0.5 w-7 bg-primary" />
          <div className="h-2.5 w-2.5 rounded-full bg-primary ring-4 ring-primary/20" />
          <div className="h-0.5 w-7 bg-primary" />
          <div className="h-2 w-2 rounded-full bg-muted-foreground" />
        </div>

        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary">
          <Layers className="h-7 w-7 text-white" />
        </div>
      </div>

      {/* Header Texts */}
      <div className="mb-10 text-center">
        <h1 className="mb-3 text-3xl font-bold tracking-tight text-foreground">
          Connect your GitHub account
        </h1>
        <p className="mx-auto max-w-[434px] text-sm leading-6 text-muted-foreground max-xl:hidden">
          Give CloudPilot access to your repositories so our AI agents can analyze your existing
          codebase, understand your application, and prepare secure AWS deployments.
        </p>
      </div>

      {/* Permissions Section */}
      <div className="mb-8 max-xl:hidden">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          What access does CloudPilot need?
        </h2>
        <div className="flex flex-col gap-4">
          {permissions.map((item, i) => (
            <div key={i} className="flex items-center gap-5 rounded-2xl border bg-muted/50 p-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-accent-border bg-accent">
                <item.icon className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h3 className="text-base font-medium text-foreground">{item.title}</h3>
                <p className="mt-1 text-sm font-light text-slate-500">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Security Box */}
      <div className="mb-10 rounded-2xl border border-accent-border bg-accent/50 p-6">
        <div className="mb-3 flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-primary" />
          <h3 className="text-base font-medium text-foreground">
            Enterprise-Grade Security Assurance
          </h3>
        </div>
        <ul className="ml-7 list-disc space-y-1 text-sm font-light text-muted-foreground marker:text-muted-foreground">
          <li>Source code is analyzed only to prepare and manage deployments.</li>
          <li>CloudPilot does not generate or replace your application source code.</li>
          <li>Sensitive credentials are handled securely and never displayed in logs.</li>
          <li>You remain in control of your repositories and deployment approvals.</li>
        </ul>
      </div>

      {/* Action Area */}
      <div className="flex flex-col items-center">
        <Button asChild className="h-14 w-full gap-2 text-base font-semibold">
          <Link href="/api/auth/login">
            <Image
              src={githubIcon}
              alt="github icon"
              width={32}
              className="h-8 w-8 invert dark:invert"
            />
            Continue With Github
          </Link>
        </Button>
        <p className="mt-6 text-center text-sm font-light text-muted-foreground">
          By connecting, you agree to authorize CloudPilot to access the permissions described
          above.
        </p>
      </div>
    </div>
  )
}
