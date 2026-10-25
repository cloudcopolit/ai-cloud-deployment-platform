import { expect, test } from '@playwright/test'
import { expectAccessible, signIn } from './helpers'

for (const colorScheme of ['light', 'dark'] as const) {
  test(`landing page explains the product and passes axe (${colorScheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme })
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1 })).toContainText('From GitHub repository to')
    await expect(page.getByRole('img', { name: 'CloudPilot' }).first()).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Meet the agents' })).toBeVisible()
    // capability honesty is part of the pitch
    await expect(page.getByRole('table', { name: /Capability status/ })).toContainText('NOT BUILT')
    await expectAccessible(page, `landing-${colorScheme}`)
  })

  test(`sign-in page carries the brand and passes axe (${colorScheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme })
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: 'Sign in to CloudPilot' })).toBeVisible()
    await expect(page.getByRole('link', { name: /Continue with GitHub/ })).toBeVisible()
    await expect(page.getByText(/graduation/i)).toHaveCount(0)
    await expectAccessible(page, `login-${colorScheme}`)
  })
}

test('agents page shows the crew and the real provider table', async ({ page }) => {
  await signIn(page, 'owner')
  await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Agents' }).click()
  await expect(page.getByRole('heading', { name: 'Agents', level: 1 })).toBeVisible()
  for (const name of ['Orchestrator', 'Analysis agent', 'Architect agent', 'Deployment engine']) {
    await expect(page.getByRole('main').getByText(name, { exact: true }).first()).toBeVisible()
  }
  await expect(page.getByRole('table', { name: /Language-model providers/ })).toBeVisible()
  await expectAccessible(page, 'agents')
})

test('landing page has no horizontal scroll on a phone @mobile', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 })
  await page.goto('/')
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
})
