import AxeBuilder from '@axe-core/playwright'
import { expect, type Page } from '@playwright/test'

export const API = process.env.E2E_API_URL ?? 'http://localhost:8100'

export const USERS = {
  owner: 'Alice — OWNER of Acme Startup',
  admin: 'Bob — ADMIN of Acme Startup',
  member: 'Carol — MEMBER of Acme Startup'
} as const

export async function signIn(page: Page, who: keyof typeof USERS) {
  await page.goto('/login')
  await page.getByLabel('Sign in as a seeded user').selectOption({ label: USERS[who] })
  await page.getByRole('button', { name: 'Developer sign-in' }).click()
  await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()
}

/** WCAG 2.2 A/AA rules; serious and critical violations fail the test. */
export async function expectAccessible(page: Page, label: string) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze()
  const bad = result.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
  expect(bad.map((v) => `${label}: ${v.id} (${v.nodes.length}) ${v.nodes[0]?.target.join(' ')}`)).toEqual([])
}

export async function openDemoProject(page: Page) {
  await page.getByRole('main').getByRole('link', { name: /Demo Shop/ }).first().click()
  await expect(page.getByRole('heading', { name: 'Repositories' })).toBeVisible()
}

/** Connect (or open, if already connected) a fake-GitHub repository from the project page. */
export async function openRepository(page: Page, fullName: string) {
  const existing = page.getByRole('link', { name: new RegExp(fullName.replace('/', '\\/')) })
  if (await existing.count()) {
    await existing.first().click()
  } else {
    await page.getByLabel('GitHub repository URL').fill(`https://github.com/${fullName}`)
    await page.getByRole('button', { name: 'Connect' }).click()
  }
  await expect(page.getByRole('heading', { name: fullName })).toBeVisible()
}
