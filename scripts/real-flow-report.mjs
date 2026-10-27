#!/usr/bin/env node
// Writes the evidence files of a real-flow run (scripts/real-flow.sh):
//   node scripts/real-flow-report.mjs changes <run-dir>          -> CHANGES.md
//   node scripts/real-flow-report.mjs result  <run-dir> <status> -> RESULT.md
// AWS calls go through scripts/aws.sh (CloudPilot's own identity). Nothing secret is written.
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'

const [mode, runDir, status = '0'] = process.argv.slice(2)
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')), '..')
const sh = (args, opts = {}) => execFileSync('sh', args, { cwd: root, encoding: 'utf8', timeout: 120_000, ...opts })
const git = (...args) => execFileSync('git', args, { cwd: root, encoding: 'utf8' }).trim()
const cairo = (d) =>
  new Intl.DateTimeFormat('en-GB', { timeZone: 'Africa/Cairo', dateStyle: 'medium', timeStyle: 'medium' }).format(d)

if (mode === 'changes') {
  const markerFile = path.join(root, 'test-runs', '.last-run-sha')
  const since = existsSync(markerFile) ? readFileSync(markerFile, 'utf8').trim() : 'd6b1dc6'
  const first = !existsSync(markerFile)
  const log = git('log', '--reverse', '--date=iso-strict', '--format=%H%x09%ad%x09%s', `${since}..HEAD`)
  const lines = [
    `# Changes since ${first ? 'the start of the deploy slice (d6b1dc6, PLANNING.md)' : `the previous run (${since.slice(0, 7)})`}`,
    '',
    `Written ${cairo(new Date())} (Africa/Cairo) for HEAD ${git('rev-parse', '--short', 'HEAD')}.`,
    ''
  ]
  for (const row of log.split('\n').filter(Boolean)) {
    const [sha, date, subject] = row.split('\t')
    const files = git('show', '--name-only', '--format=', sha).split('\n').filter(Boolean)
    const body = git('show', '-s', '--format=%b', sha).split('\n').filter((l) => l.startsWith('- ')).slice(0, 8)
    lines.push(`## ${cairo(new Date(date))} · ${sha.slice(0, 7)} · ${subject}`, '')
    for (const b of body) lines.push(b)
    if (body.length) lines.push('')
    lines.push(`Files (${files.length}): ${files.slice(0, 40).map((f) => `\`${f}\``).join(', ')}${files.length > 40 ? ', …' : ''}`, '')
  }
  const dirty = git('status', '--short').split('\n').filter(Boolean)
  lines.push('## Uncommitted at run time', '', dirty.length ? dirty.map((l) => `- \`${l}\``).join('\n') : '- none', '')
  writeFileSync(path.join(runDir, 'CHANGES.md'), lines.join('\n'))
  console.log(`    wrote ${path.join(runDir, 'CHANGES.md')}`)
  process.exit(0)
}

// ── RESULT.md ──
const stepsFile = path.join(runDir, 'steps.json')
if (!existsSync(stepsFile)) {
  writeFileSync(
    path.join(runDir, 'RESULT.md'),
    `# Real-AWS flow · FAILED before the first step was recorded

Flow exit ${status}; see the console log of scripts/real-flow.sh.
`
  )
  process.exit(0)
}
const data = JSON.parse(readFileSync(stepsFile, 'utf8'))
const { steps, facts } = data
const fmt = (ms) => (ms >= 60_000 ? `${Math.floor(ms / 60_000)} min ${Math.round((ms % 60_000) / 1000)} s` : `${(ms / 1000).toFixed(1)} s`)
const start = steps.length ? new Date(steps[0].started) : new Date()
const end = steps.length ? new Date(steps.at(-1).ended) : new Date()

// CloudTrail: events recorded under each job's role-session name (lookup can lag ~5-15 min)
const sessions = facts.sessions ?? []
const trail = []
for (const s of sessions) {
  let names = []
  for (let attempt = 0; attempt < 6; attempt += 1) {
    try {
      const out = sh([
        'scripts/aws.sh', 'cloudtrail', 'lookup-events', '--region', 'us-east-1',
        '--lookup-attributes', `AttributeKey=Username,AttributeValue=${s.session_name}`,
        '--max-results', '50', '--query', 'Events[].EventName', '--output', 'json'
      ])
      names = JSON.parse(out)
    } catch {
      names = []
    }
    if (names.length) break
    execFileSync('sh', ['-c', 'sleep 60'])
  }
  const counts = names.reduce((m, n) => ({ ...m, [n]: (m[n] ?? 0) + 1 }), {})
  trail.push({ ...s, events: names.length, top: Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8) })
}

// Cost: an estimate from the price table for the time resources existed (AWS bills ALB/IPv4
// per started hour, RDS and Fargate per second); the invoiced figure appears in Cost Explorer
// after ~24 h and is queried below for the record.
const applyStep = steps.find((s) => s.name === 'applying')
const destroyStep = steps.find((s) => s.name === 'destroyed')
let estimate = null
if (applyStep && destroyStep) {
  const prices = JSON.parse(readFileSync(path.join(root, 'ai/src/cloudpilot_ai/architecture/prices/us-east-1.json'), 'utf8')).items
  const hours = (new Date(destroyStep.ended) - new Date(applyStep.started)) / 3_600_000
  const started = Math.ceil(hours)
  estimate = {
    hours: hours.toFixed(2),
    usd:
      started * prices.alb_hour.usd +
      started * 3 * prices.public_ipv4_hour.usd +
      hours * prices.rds_postgres_t4g_micro_hour.usd +
      hours * (0.25 * prices.fargate_vcpu_hour.usd + 0.5 * prices.fargate_gb_hour.usd) +
      (prices.rds_gp3_gb_month.usd * 20 * hours) / 730 +
      (prices.secretsmanager_secret_month.usd * hours) / 730
  }
}
let invoiced = 'not available'
try {
  const day = new Date().toISOString().slice(0, 10)
  const next = new Date(Date.now() + 86_400_000).toISOString().slice(0, 10)
  const out = sh([
    'scripts/aws.sh', 'ce', 'get-cost-and-usage', '--time-period', `Start=${day},End=${next}`,
    '--granularity', 'DAILY', '--metrics', 'UnblendedCost', '--query',
    'ResultsByTime[0].Total.UnblendedCost', '--output', 'json'
  ])
  const c = JSON.parse(out)
  invoiced = `${Number(c.Amount).toFixed(4)} ${c.Unit} for the account on ${day} (UTC) so far; Cost Explorer lags by up to 24 h`
} catch (e) {
  invoiced = `Cost Explorer query failed: ${String(e).split('\n')[0].slice(0, 160)}`
}

const shots = existsSync(path.join(runDir, 'screenshots')) ? readdirSync(path.join(runDir, 'screenshots')).sort() : []
const passed = status === '0' && steps.every((s) => s.status === 'pass')
const dc = facts.destroy_check ?? {}
const lines = [
  `# Real-AWS flow · ${passed ? 'PASSED' : 'FAILED'}`,
  '',
  `- Start: ${cairo(start)} · End: ${cairo(end)} (Africa/Cairo) · total ${fmt(end - start)}`,
  `- Commit: ${git('rev-parse', '--short', 'HEAD')} · Deployment: ${facts.deployment_id ?? '—'} · final status ${facts.final_status ?? '—'}`,
  `- Allowed CIDR (ALB ingress): ${facts.allowed_cidr ?? '—'}`,
  '',
  '## Steps',
  '',
  '| # | Step | Result | Duration | Note |',
  '|---|---|---|---|---|',
  ...steps.map((s) => `| ${s.n} | ${s.name} | ${s.status === 'pass' ? 'pass' : '**FAIL**'} | ${fmt(s.ms)} | ${(s.note ?? '').replaceAll('|', '/').replaceAll('\n', ' ')} |`),
  '',
  '## Health check',
  '',
  '```json',
  JSON.stringify({ by_cloudpilot_runner: facts.health ?? null, from_the_test_machine: facts.health_from_test_machine ?? null }, null, 2),
  '```',
  '',
  '## Zero-resource check after destroy',
  '',
  `- Tagged resources still existing (cloudpilot:deployment-id=${facts.deployment_id}): **${(dc.remaining ?? ['?']).length}**`,
  `- Resources left in OpenTofu state: ${dc.remaining_in_state ?? '—'}`,
  `- Listed by the tagging index but confirmed deleted with the owning service: ${(dc.indexed_but_gone ?? []).length}`,
  `- ECS task definition revisions deleted: ${dc.deleted_task_definitions ?? '—'} · check attempts: ${dc.attempts ?? '—'} · checked ${dc.checked_at ?? '—'}`,
  '',
  '## CloudTrail sessions',
  '',
  '| Session name | Job | Events found | Most frequent |',
  '|---|---|---|---|',
  ...trail.map((t) => `| \`${t.session_name}\` | ${t.action} | ${t.events} | ${t.top.map(([n, c]) => `${n}×${c}`).join(', ')} |`),
  '',
  '## Cost',
  '',
  estimate
    ? `- Estimate for this run: **$${estimate.usd.toFixed(4)}** (${estimate.hours} h of resources; ALB and public IPv4 billed per started hour, RDS and Fargate per second, from the price table, pricing as of its date).`
    : '- Estimate: not computed (apply or destroy did not run).',
  `- Invoiced (Cost Explorer): ${invoiced}`,
  `- Monthly estimate of the plan: ${facts.cost_estimate ? `$${facts.cost_estimate.monthly_total}` : '—'}`,
  '',
  '## Audit trail',
  '',
  ...(facts.audit ?? []).map((a) => `- ${a}`),
  '',
  '## Screenshots',
  '',
  ...shots.map((f) => `- screenshots/${f}`),
  ''
]
writeFileSync(path.join(runDir, 'RESULT.md'), lines.join('\n'))
console.log(`    wrote ${path.join(runDir, 'RESULT.md')}`)
