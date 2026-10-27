/*
 * CloudPilot end to end against REAL AWS, through the UI, as a person would do it:
 * sign in -> connect repo -> analysis -> architecture with real prices -> AWS account
 * (onboarding stack + STS verification) -> OpenTofu plan + cost -> approval bound to the
 * plan hash -> apply -> real HTTP health check -> destroy -> zero tagged resources.
 *
 * Run only through scripts/real-flow.sh (it sets RUN_DIR and IMAGE_URI). Never in CI.
 */
import { execFileSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'

import { expect, test, type Page } from '@playwright/test'

const RUN_DIR = process.env.RUN_DIR ?? ''
const IMAGE_URI = process.env.IMAGE_URI ?? ''
const API = process.env.REAL_API_URL ?? 'http://localhost:8000'
const REPO_URL = 'https://github.com/cloudpilot-examples/reference-app'
const ACCOUNT_ID = process.env.AWS_SANDBOX_ACCOUNT_ID ?? ''
const REPO_ROOT = path.resolve(__dirname, '..', '..')

type StepRecord = { n: number; name: string; status: 'pass' | 'fail'; started: string; ended: string; ms: number; note?: string }
const steps: StepRecord[] = []
const facts: Record<string, unknown> = {}
let shot = 0

/** Africa/Cairo wall-clock time as HHMM-SS (screenshot names) */
function cairoClock(d = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Africa/Cairo',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23'
  }).formatToParts(d)
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '00'
  return `${get('hour')}${get('minute')}-${get('second')}`
}

async function snap(page: Page, label: string) {
  shot += 1
  const dir = path.join(RUN_DIR, 'screenshots')
  mkdirSync(dir, { recursive: true })
  const file = path.join(dir, `${String(shot).padStart(2, '0')}_${cairoClock()}_${label}.png`)
  // the External ID is an identifier, not a secret, but it is masked anyway
  await page.screenshot({ path: file, fullPage: true, mask: [page.locator('code:has-text("cp-")')] })
  return file
}

async function step<T>(page: Page, name: string, body: () => Promise<T>): Promise<T> {
  const started = new Date()
  try {
    const value = await body()
    const ended = new Date()
    steps.push({ n: steps.length + 1, name, status: 'pass', started: started.toISOString(), ended: ended.toISOString(), ms: +ended - +started })
    return value
  } catch (error) {
    const ended = new Date()
    steps.push({
      n: steps.length + 1,
      name,
      status: 'fail',
      started: started.toISOString(),
      ended: ended.toISOString(),
      ms: +ended - +started,
      note: String(error).slice(0, 600)
    })
    await snap(page, `error-${name}`).catch(() => undefined)
    throw error
  } finally {
    writeFileSync(path.join(RUN_DIR, 'steps.json'), JSON.stringify({ steps, facts }, null, 2))
  }
}

/** waits for `done` while taking a progress screenshot every `everyMs` (apply and destroy take minutes) */
async function waitWithProgress(page: Page, done: () => Promise<boolean>, label: string, timeoutMs: number, everyMs = 4 * 60_000) {
  const deadline = Date.now() + timeoutMs
  let last = Date.now()
  while (Date.now() < deadline) {
    if (await done()) return
    await page.waitForTimeout(10_000)
    if (Date.now() - last >= everyMs) {
      await snap(page, label)
      last = Date.now()
    }
  }
  throw new Error(`${label}: not finished after ${Math.round(timeoutMs / 60_000)} min`)
}

async function api<T>(page: Page, method: 'GET' | 'POST', url: string, data?: unknown): Promise<T> {
  const res = await page.request.fetch(`${API}${url}`, {
    method,
    data,
    headers: { Origin: 'http://localhost:3000' }
  })
  expect(res.ok(), `${method} ${url} -> ${res.status()}`).toBeTruthy()
  return (await res.json()) as T
}

test('real AWS: repository to a health-checked deployment and a clean destroy', async ({ page }) => {
  expect(RUN_DIR, 'RUN_DIR (set by scripts/real-flow.sh)').not.toBe('')
  expect(IMAGE_URI).toMatch(/@sha256:[0-9a-f]{64}$/)
  expect(ACCOUNT_ID).toMatch(/^\d{12}$/)

  await step(page, 'login', async () => {
    await page.goto('/login')
    await snap(page, 'login-page')
    await page.getByLabel('Sign in as a seeded user').selectOption({ index: 0 }) // Alice, OWNER
    await page.getByRole('button', { name: 'Developer sign-in' }).click()
    await expect(page.getByRole('heading', { name: 'Overview', level: 1 })).toBeVisible()
    await snap(page, 'overview')
  })

  facts.repository_path = await step(page, 'repo-connected', async () => {
    await page.getByRole('main').getByRole('link', { name: /Demo Shop/ }).first().click()
    await expect(page.getByRole('heading', { name: 'Repositories' })).toBeVisible()
    await snap(page, 'project-repositories')
    const existing = page.getByRole('link', { name: /cloudpilot-examples\/reference-app/ })
    if (await existing.count()) {
      await existing.first().click()
    } else {
      await page.getByLabel('GitHub repository URL').fill(REPO_URL)
      await snap(page, 'connect-repository-form')
      await page.getByRole('button', { name: 'Connect' }).click()
    }
    await expect(page.getByRole('heading', { name: 'cloudpilot-examples/reference-app' })).toBeVisible()
    await snap(page, 'repo-connected')
    return new URL(page.url()).pathname
  })

  await step(page, 'analysis-done', async () => {
    await page.getByRole('button', { name: 'Analyze this commit' }).click()
    await expect(page.getByRole('heading', { name: 'Repository analysis' })).toBeVisible()
    await page.waitForTimeout(3_000) // the live agent trace, mid-run
    await snap(page, 'analysis-running')
    await expect(page.getByText('Analysis finished.')).toBeVisible({ timeout: 180_000 })
    await expect(page.getByRole('main').getByText('checked the result')).toBeVisible()
    facts.analysis_url = page.url()
    await snap(page, 'analysis-done')
  })

  await step(page, 'architecture', async () => {
    await page.getByRole('button', { name: 'Propose an architecture' }).click()
    await expect(page.getByRole('heading', { name: /Architecture · version \d+/ })).toBeVisible({ timeout: 60_000 })
    await snap(page, 'architecture-drawing')
    await expect(page.getByText(/Reasoning · \d+ steps/)).toBeVisible({ timeout: 60_000 })
    await expect(page.getByText(/Deterministic plan for the container-postgres archetype/)).toBeVisible()
    facts.architecture_url = page.url()
    facts.architecture_monthly = await page.getByRole('heading', { name: 'Monthly estimate' }).locator('..').locator('..').innerText()
    await snap(page, 'architecture')
  })

  await step(page, 'aws-account-verified', async () => {
    await page.goto('/aws')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await snap(page, 'aws-accounts')
    const card = page.getByRole('listitem', { name: `AWS account ${ACCOUNT_ID}` })
    const verified = card.filter({ hasText: 'Verified' })
    if ((await verified.count()) === 0) {
      if ((await card.count()) === 0) {
        await page.getByLabel('AWS account ID').fill(ACCOUNT_ID)
        await page.getByRole('button', { name: 'Connect AWS account' }).click()
        await expect(card.first()).toBeVisible()
        await snap(page, 'aws-account-connected-onboarding')
      }
      // the customer's step: deploy the generated onboarding template in their account
      const teams = await api<{ id: string; name: string }[]>(page, 'GET', '/teams')
      const accounts = (
        await Promise.all(teams.map((t) => api<{ id: string; aws_account_id: string }[]>(page, 'GET', `/teams/${t.id}/aws-accounts`)))
      ).flat()
      const account = accounts.find((a) => a.aws_account_id === ACCOUNT_ID)
      expect(account).toBeTruthy()
      const onboarding = await api<{ template: string; stack_name: string }>(page, 'GET', `/aws-accounts/${account!.id}/onboarding`)
      const templateRel = path.relative(REPO_ROOT, path.join(RUN_DIR, 'cloudpilot-onboarding.json')).split(path.sep).join('/')
      writeFileSync(path.join(RUN_DIR, 'cloudpilot-onboarding.json'), onboarding.template)
      execFileSync(
        'sh',
        [
          'scripts/aws.sh',
          'cloudformation',
          'deploy',
          '--region',
          'us-east-1',
          '--stack-name',
          onboarding.stack_name,
          '--template-file',
          `/work/${templateRel}`,
          '--capabilities',
          'CAPABILITY_NAMED_IAM',
          '--no-fail-on-empty-changeset'
        ],
        { cwd: REPO_ROOT, stdio: 'inherit', timeout: 15 * 60_000 }
      )
      facts.onboarding_stack = onboarding.stack_name
      await page.reload()
      await snap(page, 'aws-onboarding-stack-deployed')
    }
    await card.first().getByRole('button', { name: /Verify (connection|again)/ }).click()
    await expect(card.first().getByText('Verified', { exact: true })).toBeVisible({ timeout: 60_000 })
    await expect(card.first().getByText('AssumeRole without the External ID is denied')).toBeVisible()
    await snap(page, 'aws-account-verified')
  })

  const deploymentPath = await step(page, 'plan-and-cost', async () => {
    await page.goto(String(facts.architecture_url).replace('?build=1', ''))
    await snap(page, 'architecture-before-deploy')
    await page.getByRole('link', { name: 'Deploy this architecture' }).click()
    await expect(page.getByRole('heading', { name: 'Plan a deployment' })).toBeVisible()
    await snap(page, 'deploy-form')
    await page.getByLabel('Container image, pinned by digest').fill(IMAGE_URI)
    await page.getByRole('button', { name: 'Use my IP' }).click()
    await expect(page.getByLabel('Who may reach the load balancer')).toHaveValue(/\/32$/)
    facts.allowed_cidr = await page.getByLabel('Who may reach the load balancer').inputValue()
    await snap(page, 'deploy-form-filled')
    await page.getByRole('button', { name: 'Create the OpenTofu plan' }).click()
    await expect(page.getByRole('heading', { name: /Deployment [0-9a-f]{8}/ })).toBeVisible()
    await snap(page, 'planning')
    const awaiting = page.getByText('Awaiting approval', { exact: true })
    await waitWithProgress(page, () => awaiting.isVisible(), 'planning-progress', 15 * 60_000, 2 * 60_000)
    await expect(page.getByRole('heading', { name: 'Cost of this plan' })).toBeVisible()
    await snap(page, 'plan-and-cost')
    return new URL(page.url()).pathname
  })
  const deploymentId = deploymentPath.split('/').pop() ?? ''
  facts.deployment_id = deploymentId

  await step(page, 'approved', async () => {
    await page.getByLabel(/I reviewed the resources/).check()
    await snap(page, 'approval-review')
    await page.getByRole('button', { name: 'Approve plan' }).click()
    await expect(page.getByRole('button', { name: 'Apply this plan to AWS' })).toBeVisible()
    await snap(page, 'approved')
  })

  await step(page, 'applying', async () => {
    await page.getByRole('button', { name: 'Apply this plan to AWS' }).click()
    await expect(page.getByText(/^(Applying|Apply queued)$/).first()).toBeVisible({ timeout: 120_000 })
    await snap(page, 'apply-started')
    await expect(page.getByText('Applying', { exact: true })).toBeVisible({ timeout: 300_000 })
    await page.waitForTimeout(60_000) // let a few resources land, for the screenshot
    await snap(page, 'applying')
  })

  await step(page, 'health-check-passed', async () => {
    const finished = page.getByText(/^(Live|Failed)$/).first()
    await waitWithProgress(page, () => finished.isVisible(), 'applying-progress', 45 * 60_000)
    const d = await api<Record<string, unknown>>(page, 'GET', `/deployments/${deploymentId}`)
    facts.health = d.health
    facts.outputs = d.outputs
    facts.cost_estimate = d.cost_estimate
    await expect(page.getByText('Your service is live')).toBeVisible()
    // prove it from outside CloudPilot too: the health route answers from this machine
    const health = (d.health as { url: string }).url
    const res = await page.request.get(health, { timeout: 20_000 })
    facts.health_from_test_machine = { url: health, status: res.status(), body: (await res.text()).slice(0, 300) }
    expect(res.status()).toBe(200)
    await snap(page, 'health-check-passed')
    // the deployed application itself, in the browser
    const app = await page.context().newPage()
    await app.goto(health)
    await snap(app, 'deployed-app-health-endpoint')
    await app.close()
  })

  await step(page, 'destroyed', async () => {
    await page.getByLabel('Type "destroy" to confirm').fill('destroy')
    await snap(page, 'destroy-confirm')
    await page.getByRole('button', { name: 'Destroy deployment' }).click()
    await expect(page.getByText(/^(Destroying|Destroy queued)$/).first()).toBeVisible({ timeout: 120_000 })
    await snap(page, 'destroy-started')
    const gone = page.getByText(/^(Destroyed|Destroy incomplete)$/).first()
    await waitWithProgress(page, () => gone.isVisible(), 'destroying-progress', 45 * 60_000)
    const d = await api<Record<string, unknown>>(page, 'GET', `/deployments/${deploymentId}`)
    facts.destroy_check = d.destroy_check
    facts.sessions = d.sessions
    facts.final_status = d.status
    facts.audit = (await api<{ action: string; created_at: string; plan_hash: string | null }[]>(page, 'GET', `/deployments/${deploymentId}/audit`)).map(
      (e) => `${e.created_at} ${e.action}${e.plan_hash ? ` plan=${e.plan_hash.slice(0, 12)}` : ''}`
    )
    await expect(page.getByText('Destroyed', { exact: true })).toBeVisible()
    await snap(page, 'destroyed')
    await page.getByRole('heading', { name: 'Audit trail' }).scrollIntoViewIfNeeded()
    await snap(page, 'audit-trail')
  })
})
