import { defineConfig, devices } from '@playwright/test'

/*
 * The REAL-AWS full flow (scripts/real-flow.sh only; never scripts/e2e.sh or CI).
 * It drives the dev stack on :3000 against the sandbox AWS account and destroys what it
 * creates. Evidence goes to test-runs/<date>/run-<time>/ (git-ignored).
 */
export default defineConfig({
  testDir: './e2e-real',
  timeout: 100 * 60_000, // plan + RDS apply + health + destroy
  expect: { timeout: 30_000 },
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.REAL_BASE_URL ?? 'http://localhost:3000',
    viewport: { width: 1440, height: 1000 },
    colorScheme: 'dark',
    trace: 'off',
    screenshot: 'off'
  },
  projects: [{ name: 'real-aws', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } }]
})
