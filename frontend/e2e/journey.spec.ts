import { expect, test } from '@playwright/test'
import { expectAccessible, openDemoProject, openRepository, signIn } from './helpers'

test.describe.configure({ mode: 'serial' })

test('connect a repository, pick a commit, watch the analysis live, read the report', async ({ page }) => {
  await signIn(page, 'owner')
  await expectAccessible(page, 'overview')
  await openDemoProject(page)
  await expectAccessible(page, 'project')

  await openRepository(page, 'e2e/fastapi-shop')
  await expect(page.getByLabel('Branch', { exact: true })).toHaveValue('main')
  // branch picker lists real (fake-GitHub) branches; commit picker preselects the head
  await expect(page.getByRole('radio', { name: /Add orders endpoint/ })).toBeChecked()
  await page.getByLabel('Branch', { exact: true }).selectOption('feature/payments')
  await expect(page.getByRole('radio', { name: /Payments work in progress/ })).toBeChecked()
  await page.getByLabel('Branch', { exact: true }).selectOption('main')
  await page.getByRole('radio', { name: /Initial FastAPI service/ }).check()
  await expectAccessible(page, 'repository')

  await page.getByRole('button', { name: 'Analyze this commit' }).click()
  await expect(page.getByRole('heading', { name: 'Repository analysis' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Agent activity' })).toBeVisible()
  await expect(page.getByText('Analysis finished.')).toBeVisible({ timeout: 60_000 })

  // the live view shows which agents ran and every step
  await expect(page.getByRole('main').getByText('started the job')).toBeVisible()
  await expect(page.getByRole('main').getByText('checked the result')).toBeVisible()
  await expect(page.getByRole('main').getByText('Analysis agent', { exact: true })).toBeVisible()
  await expect(page.getByText('Scanned for committed secrets')).toBeVisible()
  await expect(page.getByText('No committed secrets found')).toBeVisible()
  await expect(page.getByText('No language model used (deterministic)').first()).toBeVisible()

  // the report is built from the repository's real files
  const services = page.getByRole('table', { name: 'Detected services' })
  await expect(services.getByRole('row', { name: /fastapi-shop/ })).toContainText('8000')
  await expect(services).toContainText('/health')
  await expect(page.getByText('CloudPilot can deploy this automatically.')).toBeVisible()
  await expectAccessible(page, 'analysis')
  // the agent trace: every step with its result, raw output one click away
  await expect(page.getByRole('progressbar', { name: 'Steps finished' })).toBeVisible()
  await page.getByRole('button', { name: /Read the repository/ }).click()
  await expect(page.getByText('← output')).toBeVisible()
  await page.emulateMedia({ colorScheme: 'dark' })
  await expectAccessible(page, 'analysis-black')
  await page.emulateMedia({ colorScheme: 'light' })

  // hand the report to the Architect agent; its proposal is drawn with official AWS icons
  await page.getByRole('button', { name: 'Propose an architecture' }).click()
  await expect(page.getByRole('heading', { name: /Architecture · version \d+/ })).toBeVisible({ timeout: 30_000 })
  const diagram = page.getByRole('figure', { name: 'Architecture diagram' })
  await expect(diagram.getByRole('button', { name: /Application Load Balancer/ })).toBeVisible()
  await expect(diagram.locator('img[src="/aws-icons/ecs_service.svg"]')).toBeVisible()
  // the accessible alternative lists every component
  await expect(page.getByRole('table', { name: /Every component/ })).toContainText('Amazon Elastic Container Service')
  // honest labelling of the prototype
  await expect(page.getByText('Prototype architect: same template for every repository')).toBeVisible()
  await diagram.getByRole('button', { name: /Application Load Balancer/ }).click()
  await expect(page.getByText('Why the Architect chose it')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0) // closed, incl. its exit animation
  await page.getByRole('button', { name: 'About the Architect agent' }).first().click()
  await expect(page.getByRole('dialog')).toContainText('Writes Terraform')
  await page.keyboard.press('Escape')
  await expectAccessible(page, 'architecture')
  await page.emulateMedia({ colorScheme: 'dark' })
  await expectAccessible(page, 'architecture-black')
})

test('a blocked analysis asks a question and the answer unblocks it', async ({ page }) => {
  await signIn(page, 'owner')
  await openDemoProject(page)
  await openRepository(page, 'e2e/sqlite-notes')
  await page.getByRole('button', { name: 'Analyze this commit' }).click()
  await expect(page.getByText(/needs your input/)).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('REQUIRES_LOCAL_ONLY_RESOURCE')).toBeVisible()
  await expectAccessible(page, 'blocked analysis')

  await page.getByLabel(/SQLite data does not survive/).fill('postgresql')
  await page.getByRole('button', { name: 'Re-run the analysis with these answers' }).click()
  await expect(page.getByText('Analysis finished.')).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('SQLITE_PRIMARY_DATABASE').first()).toBeAttached()
})

test('a MEMBER can analyze but cannot connect repositories', async ({ page }) => {
  await signIn(page, 'member')
  await openDemoProject(page)
  await page.getByLabel('GitHub repository URL').fill('https://github.com/e2e/static-site')
  await page.getByRole('button', { name: 'Connect' }).click()
  await expect(page.getByRole('main').getByRole('alert')).toContainText('requires ADMIN role')
})

test('another tenant’s project is not found, not forbidden', async ({ page }) => {
  await signIn(page, 'owner')
  await page.goto('/projects/00000000-0000-4000-8000-000000000000')
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Not found')
})

test('the plan limit is explained when creating one project too many', async ({ page }) => {
  await signIn(page, 'owner')
  await page.getByLabel('Project name').fill('Second project')
  await page.getByRole('button', { name: 'Create project' }).click()
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Plan limit')
})

test('the UI says so when the API is unreachable', async ({ page }) => {
  await signIn(page, 'owner')
  await openDemoProject(page)
  await page.route('**/projects/*/repositories', (route) => route.abort('connectionrefused'))
  await page.getByLabel('GitHub repository URL').fill('https://github.com/e2e/static-site')
  await page.getByRole('button', { name: 'Connect' }).click()
  await expect(page.getByRole('main').getByRole('alert')).toContainText('cannot be reached')
})

test('mobile layout has no horizontal scroll @mobile', async ({ page }) => {
  await signIn(page, 'owner')
  await openDemoProject(page)
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
})
