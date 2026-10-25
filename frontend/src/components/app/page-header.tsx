import Link from 'next/link'
import { ChevronRight } from 'lucide-react'

export type Crumb = { label: string; href?: string }

export function PageHeader({
  title,
  crumbs = [],
  description,
  actions
}: {
  title: string
  crumbs?: Crumb[]
  description?: React.ReactNode
  actions?: React.ReactNode
}) {
  return (
    <div className="space-y-3 border-b pb-5">
      {crumbs.length ? (
        <nav aria-label="Breadcrumb">
          <ol className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
            {crumbs.map((c, i) => (
              <li key={`${c.label}-${i}`} className="flex items-center gap-1">
                {i > 0 ? <ChevronRight className="size-3.5" aria-hidden /> : null}
                {c.href ? (
                  <Link href={c.href} className="hover:text-foreground hover:underline">
                    {c.label}
                  </Link>
                ) : (
                  <span aria-current="page">{c.label}</span>
                )}
              </li>
            ))}
          </ol>
        </nav>
      ) : null}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-1">
          <h1 className="truncate text-2xl font-semibold tracking-tight">{title}</h1>
          {description ? <div className="text-sm text-muted-foreground">{description}</div> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
    </div>
  )
}
