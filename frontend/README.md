## Tech stack

| Part            | Technology                                       |
| --------------- | ------------------------------------------------ |
| Framework       | Next.js 16 (App Router, Turbopack)               |
| Language        | TypeScript (strict)                              |
| Styling         | Tailwind CSS v4                                  |
| Components      | shadcn/ui                                        |
| Icons           | Lucide                                           |
| Validation      | Zod                                              |
| HTTP client     | Axios (browser) + native `fetch` (server)        |
| Auth            | Cookie-based JWT — issued by the FastAPI backend |
| Package manager | pnpm                                             |

Not used: `next-auth`, tokens in `localStorage`, refresh tokens.

---

## Prerequisites

- Node.js 24 LTS (the version CI uses, from `.nvmrc`; Next.js 16 requires at least 20.9)
- pnpm (`npm i -g pnpm`); it switches to the version pinned in `package.json` (`packageManager`, currently 12.4.1)
- Backend running at `http://localhost:8000` (only for `pnpm dev`; lint, tests, and `pnpm build` do not need it)

---

## Environment

Copy `.env.example` to `.env.local`:

```bash
cp .env.example .env.local
```

| Variable              | Example                 | Purpose                                 |
| --------------------- | ----------------------- | --------------------------------------- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Used in the browser (login link, Axios) |

> Use `localhost` everywhere, never `127.0.0.1`. Cookies are host-bound.

---

## How to run

```bash
pnpm install
pnpm dev
```

Open http://localhost:3000.

Make sure the backend is running in a separate terminal (see backend README).

---

## What we implemented

| Area                                                | Status |
| --------------------------------------------------- | ------ |
| Next.js 16 + TypeScript + Tailwind v4 scaffold      | Done   |
| shadcn/ui setup                                     | Done   |
| Zod schemas matching FastAPI responses              | Done   |
| Login page (`/login`) with GitHub button            | Done   |
| Error banner for `?error=github_failed`             | Done   |
| Route protection via `proxy.ts`                     | Done   |
| Server-side session (`getCurrentUser`)              | Done   |
| Protected dashboard layout + user menu              | Done   |
| Logout flow                                         | Done   |
| Suspense boundaries for Next.js 16 Cache Components | Done   |

### Planned

- Projects list page
- Repository connection (GitHub App)
- Architecture viewer / editor
- Deployment history
- Team settings
- Theme toggle

---

## Auth flow (short version)

1. User visits `/dashboard` → proxy redirects to `/login`
2. Click "Continue with GitHub" → full-page link to `http://localhost:8000/auth/github/login`
3. Backend does OAuth, sets `access_token` HttpOnly cookie, redirects to `/dashboard`
4. Middleware sees cookie → allows
5. Layout calls `/auth/me` → renders user

**On failure:** backend redirects to `/login?error=github_failed`.

---

## Scripts

| Command          | Purpose                                                       |
| ---------------- | ------------------------------------------------------------- |
| `pnpm dev`       | Dev server (Turbopack)                                        |
| `pnpm build`     | Production build                                              |
| `pnpm start`     | Run production build                                          |
| `pnpm lint`      | ESLint                                                        |
| `pnpm typecheck` | Generate Next.js route/env types, then `tsc --noEmit`         |
| `pnpm test`      | Vitest unit tests (`src/**/*.test.ts`)                        |

CI (`Frontend checks`) runs `pnpm install --frozen-lockfile`, `lint`, `typecheck`, `test`, and `build` on every pull request. If you change dependencies, commit the updated `pnpm-lock.yaml`.

Tests currently cover route protection in `src/proxy.ts` and the Zod schemas that mirror backend responses. No formatter (such as Prettier) is configured yet.

Add a shadcn component:

```bash
pnpm dlx shadcn@latest add <component>
```

---

## Notes

- Next.js 16 requires dynamic reads (`searchParams`, `cookies()`, uncached `fetch`) to live inside `<Suspense>`. Static shell outside, dynamic content inside.
- The `access_token` cookie is HttpOnly — JavaScript cannot read it. Get user data via `/auth/me`, never by decoding the JWT.
- No refresh token yet — JWT expires after 30 minutes; user re-logs in.
