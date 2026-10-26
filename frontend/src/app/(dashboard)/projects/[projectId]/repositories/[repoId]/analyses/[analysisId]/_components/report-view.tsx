'use client'

import { useState } from 'react'
import { AlertTriangle, Check, Info, OctagonX, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import type { Finding, Report } from '@/lib/api/schemas'

const METHOD_LABEL = {
  container: 'Containers (ECS Fargate behind a load balancer)',
  static_site: 'Static website (S3, with CloudFront on real AWS)',
  serverless: 'Serverless functions',
  unsupported: 'Not deployable yet'
} as const

const STORE_LABEL: Record<string, string> = {
  postgresql: 'PostgreSQL',
  mysql: 'MySQL',
  mariadb: 'MariaDB',
  mongodb: 'MongoDB',
  redis: 'Redis',
  kafka: 'Kafka',
  rabbitmq: 'RabbitMQ',
  elasticsearch: 'Elasticsearch / OpenSearch',
  sqlite: 'SQLite',
  memcached: 'Memcached',
  minio: 'MinIO',
  nats: 'NATS',
  cassandra: 'Cassandra',
  s3: 'S3',
  sqs: 'SQS',
  dynamodb: 'DynamoDB'
}

function Section({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-base font-semibold">
        {title}
        {count !== undefined ? <span className="ml-2 font-mono text-sm font-normal text-muted-foreground">{count}</span> : null}
      </h3>
      {children}
    </section>
  )
}

function FindingList({ findings }: { findings: Finding[] }) {
  return (
    <ul className="space-y-2">
      {findings.map((f, i) => {
        const Icon = f.severity === 'BLOCKER' ? OctagonX : f.severity === 'WARNING' ? AlertTriangle : Info
        const tone = f.severity === 'BLOCKER' ? 'text-destructive' : f.severity === 'WARNING' ? 'text-warning' : 'text-info'
        return (
          <li key={`${f.code}-${i}`} className="rounded-lg border p-3 text-sm">
            <p className="flex items-start gap-2">
              <Icon className={`mt-0.5 size-4 shrink-0 ${tone}`} aria-hidden />
              <span>
                <span className={`font-mono text-xs ${tone}`}>
                  {f.severity} · {f.code}
                </span>
                <span className="block">{f.message}</span>
              </span>
            </p>
            {f.suggested_action ? <p className="mt-1 pl-6 text-muted-foreground">{f.suggested_action}</p> : null}
            {f.evidence.length ? (
              <p className="mt-1 pl-6 font-mono text-xs text-muted-foreground">
                {f.evidence
                  .map((e) => `${e.file_path}${e.line_start ? `:${e.line_start}` : ''}`)
                  .join(', ')}
              </p>
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}

function Paged<T>({ items, render, page = 60 }: { items: T[]; render: (item: T, i: number) => React.ReactNode; page?: number }) {
  const [shown, setShown] = useState(page)
  return (
    <>
      {items.slice(0, shown).map(render)}
      {items.length > shown ? (
        <li className="list-none pt-2">
          <Button type="button" variant="outline" size="sm" onClick={() => setShown(items.length)}>
            Show all {items.length}
          </Button>
        </li>
      ) : null}
    </>
  )
}

export function ReportView({ report }: { report: Report }) {
  const rec = report.recommendation
  const runtimeDeps = report.dependencies.filter((d) => !d.dev_only)
  return (
    <div className="space-y-8">
      <Section title="Summary">
        <p className="text-sm">{report.summary}</p>
        <p className="text-xs text-muted-foreground">
          {report.meta.files_scanned} files read, {report.meta.files_skipped} skipped
          {report.meta.truncated ? ' (limit reached: results may be incomplete)' : ''} ·{' '}
          {report.meta.model ? `model ${report.meta.model}` : 'deterministic detectors, no language model'} · overall
          confidence {Math.round(report.overall_confidence * 100)}% · {report.meta.analyzer_version}
        </p>
      </Section>

      {rec ? (
        <Section title="Recommended deployment">
          <div className="rounded-xl border p-4">
            <p className="font-medium">{METHOD_LABEL[rec.method]}</p>
            <p className="mt-1 flex items-center gap-1.5 text-sm">
              {rec.automated_by_cloudpilot ? (
                <>
                  <Check className="size-4 text-success" aria-hidden /> CloudPilot can deploy this automatically.
                </>
              ) : (
                <>
                  <X className="size-4 text-warning" aria-hidden /> CloudPilot cannot deploy this automatically yet.
                </>
              )}
            </p>
            <p className="mt-2 text-sm text-muted-foreground">{rec.reasoning}</p>
          </div>
        </Section>
      ) : null}

      <Section title="Services" count={report.services.length}>
        {report.services.length === 0 ? (
          <p className="text-sm text-muted-foreground">No runnable service was detected.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Detected services</caption>
              <thead className="bg-muted/50 text-xs text-muted-foreground">
                <tr>
                  <th scope="col" className="p-2.5 font-medium">Name</th>
                  <th scope="col" className="p-2.5 font-medium">Path</th>
                  <th scope="col" className="p-2.5 font-medium">Stack</th>
                  <th scope="col" className="p-2.5 font-medium">Port</th>
                  <th scope="col" className="p-2.5 font-medium">Health</th>
                  <th scope="col" className="p-2.5 font-medium">Dockerfile</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {report.services.map((s) => (
                  <tr key={s.name}>
                    <th scope="row" className="p-2.5 font-medium">{s.name}</th>
                    <td className="p-2.5 font-mono text-xs">{s.path}</td>
                    <td className="p-2.5">
                      {[s.language, s.framework].filter(Boolean).join(' · ') || '—'}
                      <span className="block text-xs text-muted-foreground">{s.service_type}</span>
                    </td>
                    <td className="p-2.5 font-mono">
                      {s.port ?? '—'}
                      {typeof s.metadata.port_source === 'string' ? (
                        <span className="block font-sans text-xs text-muted-foreground">{s.metadata.port_source}</span>
                      ) : null}
                    </td>
                    <td className="p-2.5 font-mono text-xs">{s.health_endpoint ?? '—'}</td>
                    <td className="p-2.5">{s.has_dockerfile ? 'yes' : 'no'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {report.blockers.length ? (
        <Section title="Blockers" count={report.blockers.length}>
          <FindingList findings={report.blockers} />
        </Section>
      ) : null}

      {report.unsupported.length ? (
        <Section title="Unsupported" count={report.unsupported.length}>
          <ul className="space-y-1 text-sm">
            {report.unsupported.map((u) => (
              <li key={u.name}>
                <span className="font-medium">{u.name}</span>: {u.reason}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      <Section title="Data stores and messaging" count={report.data_stores.length}>
        {report.data_stores.length === 0 ? (
          <p className="text-sm text-muted-foreground">None detected.</p>
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2">
            {report.data_stores.map((d) => (
              <li key={d.engine} className="rounded-lg border p-3 text-sm">
                <span className="font-medium">{STORE_LABEL[d.engine] ?? d.engine}</span>
                <span className="block text-xs text-muted-foreground">from {d.inferred_from}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {report.warnings.length ? (
        <details className="group">
          <summary className="cursor-pointer text-base font-semibold">
            Warnings and notes <span className="font-mono text-sm font-normal text-muted-foreground">{report.warnings.length}</span>
          </summary>
          <div className="mt-2">
            <FindingList findings={report.warnings} />
          </div>
        </details>
      ) : null}

      <details>
        <summary className="cursor-pointer text-base font-semibold">
          Environment variable names <span className="font-mono text-sm font-normal text-muted-foreground">{report.env_vars.length}</span>
        </summary>
        <p className="mt-1 text-xs text-muted-foreground">Names only. CloudPilot never reads or stores their values.</p>
        <ul className="mt-2 columns-1 gap-4 font-mono text-xs sm:columns-2 lg:columns-3">
          <Paged items={report.env_vars} render={(e) => <li key={e.name} className="break-all py-0.5">{e.name}</li>} />
        </ul>
      </details>

      <details>
        <summary className="cursor-pointer text-base font-semibold">
          Languages, frameworks and dependencies{' '}
          <span className="font-mono text-sm font-normal text-muted-foreground">{runtimeDeps.length} runtime</span>
        </summary>
        <p className="mt-2 text-sm">
          {report.languages.map((l) => `${l.name} ${l.share_percent ?? '?'}%`).join(' · ') || 'No source languages detected.'}
        </p>
        <p className="mt-1 text-sm">
          {report.frameworks.map((f) => (f.version ? `${f.name} ${f.version}` : f.name)).join(' · ') || 'No frameworks detected.'}
        </p>
        <ul className="mt-2 columns-1 gap-4 font-mono text-xs sm:columns-2 lg:columns-3">
          <Paged
            items={runtimeDeps}
            render={(d, i) => (
              <li key={`${d.ecosystem}-${d.name}-${i}`} className="break-all py-0.5">
                {d.name} <span className="text-muted-foreground">({d.ecosystem})</span>
              </li>
            )}
          />
        </ul>
      </details>
    </div>
  )
}
