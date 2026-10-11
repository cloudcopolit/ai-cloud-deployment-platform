# CloudPilot

AI-assisted cloud architecture design and deployment platform for small development teams and startups.

CloudPilot connects to a GitHub repository, analyzes the application, proposes an AWS architecture, lets the user review and edit it, and (in later phases) deploys it to the user's own AWS account with Terraform. Every commit, architecture version, and deployment attempt is recorded so the history stays traceable.

> This is a graduation project. The README separates what is **implemented** from what is **planned**, so nothing here should be read as a finished feature unless it is listed as implemented.

---

## Project status

| Area | Status |
|---|---|
| PostgreSQL + SQLAlchemy 2 + Alembic setup | Implemented |
| Phase 1 tables: users, teams, team_members, plans, subscriptions, projects, repositories, branches, commits | Implemented |
| Seed script (plans + development data) | Implemented |
| GitHub sign-in (OAuth) | Implemented |
| JWT authentication in an HttpOnly cookie (also accepts `Authorization: Bearer`) | Implemented |
| CORS for the Next.js frontend | Implemented |
| Auth unit and API tests | Implemented |
| Create a personal team on first login | Planned (next) |
| Team role checks (`require_team_role`) | Planned |
| Projects, repositories (GitHub App), analysis modules | Planned |
| Architecture generation, validation, cost estimation | Planned |
| Terraform generation and controlled deployment | Planned |
| Monitoring, incidents, self-healing | Planned (later phase) |

---

## Tech stack

| Part | Technology |
|---|---|
| Language / framework | Python 3.12, FastAPI |
| Database | PostgreSQL 16 |
| ORM / migrations | SQLAlchemy 2.0, Alembic |
| Validation / settings | Pydantic, pydantic-settings |
| Authentication | GitHub OAuth for sign-in, PyJWT for tokens |
| HTTP client | httpx |
| Tests | pytest |
| Local services | Docker Compose |
| Frontend (separate team) | Next.js |

---

## Folder structure

```
backend/
├── app/
│   ├── main.py                  # Application entry point, CORS, health check
│   ├── api/router.py            # Combines feature routers
│   ├── core/
│   │   ├── config.py            # Settings read from .env
│   │   ├── security.py          # JWT create/decode
│   │   └── dependencies.py      # Shared FastAPI dependencies (DbSession)
│   ├── db/
│   │   ├── base.py              # SQLAlchemy Base + naming convention
│   │   ├── session.py           # Engine, SessionLocal, get_db
│   │   └── seed.py              # Seed script
│   ├── integrations/
│   │   └── github.py            # GitHub OAuth client (authorize URL, token, profile)
│   ├── models/                  # One file per table, all imported in __init__.py
│   └── modules/
│       └── auth/                # router, service, schemas, dependencies
├── alembic/                     # Migrations (versions/ is filled by Alembic)
├── tests/                       # pytest tests
├── docker-compose.yml
├── alembic.ini
├── pytest.ini
├── requirements.txt
├── .env.example
└── README.md
```

Layers follow one rule: **routers handle HTTP only, services hold business logic, models describe tables, schemas define API input/output.**

---

## Prerequisites

- Python 3.12
- Docker and Docker Compose
- A GitHub account (to create an OAuth App)

---

## Setup

All commands run from the `backend/` folder.

### 1. Virtual environment and packages

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Start PostgreSQL

```bash
docker compose up -d
docker ps                          # should show cloudpilot-db
```

Local development credentials (do not use these in production): user `cloudpilot`, password `cloudpilot`, database `cloudpilot`, port `5432`.

### 3. Create a GitHub OAuth App

GitHub → Settings → Developer settings → OAuth Apps → New OAuth App:

- Homepage URL: `http://localhost:8000`
- Authorization callback URL: `http://localhost:8000/auth/github/callback`

Copy the Client ID and generate a Client Secret.

### 4. Configure environment variables

Copy the example file and fill in the real values:

```bash
cp .env.example .env
```

| Variable | Example | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://cloudpilot:cloudpilot@localhost:5432/cloudpilot` | Database connection |
| `ENVIRONMENT` | `development` | Enables `dev-login`; non-development makes cookies `Secure` |
| `JWT_SECRET_KEY` | (generated, see below) | Signs JWTs |
| `GITHUB_CLIENT_ID` | from GitHub | OAuth |
| `GITHUB_CLIENT_SECRET` | from GitHub | OAuth |
| `FRONTEND_URL` | `http://localhost:3000` | CORS allowed origin and post-login redirect |

Generate a JWT secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`.env` is ignored by git. Only `.env.example` (with fake values) is committed.

### 5. Create the tables

```bash
alembic revision --autogenerate -m "identity subscription project source tables"
```

Open the new file in `alembic/versions/` and check that `upgrade()` creates all nine tables (it must not be only `pass`). Then:

```bash
alembic upgrade head
```

If the migration file already exists in the repository, skip the `revision` command and run only `alembic upgrade head`.

### 6. Seed the database

```bash
python -m app.db.seed
```

The script is idempotent: running it again does not create duplicates. It creates:

- Reference data: `FREE` and `STANDARD` plans
- Development data: users Alice (OWNER, github id `1001`), Bob (ADMIN, `1002`), Carol (MEMBER, `1003`), a team "Acme Startup" with a Free subscription, a project "Demo Shop", a repository, the `main` deployment branch, and three commits

### 7. Run the API

```bash
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Interactive docs (Swagger): http://localhost:8000/docs

---

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health/db` | No | Checks the database connection |
| GET | `/auth/github/login` | No | Starts GitHub sign-in (redirects to GitHub) |
| GET | `/auth/github/callback` | No | GitHub returns here; creates or updates the user, sets the cookie, redirects to the frontend |
| GET | `/auth/me` | Yes | Returns the current user |
| POST | `/auth/logout` | No | Clears the auth cookie |
| POST | `/auth/dev-login` | No | Development only: sign in as a seeded user (returns 404 outside `development`) |

### Authentication flow

```
Browser → GET /auth/github/login
        ← redirect to GitHub (random "state" saved in an HttpOnly cookie)
GitHub  → redirects to /auth/github/callback?code=...&state=...
Backend → checks state, exchanges the code, fetches the GitHub profile,
          creates or updates the user, sets the "access_token" cookie,
          redirects to {FRONTEND_URL}/dashboard
```

- The JWT contains only the user id (`sub`) and timestamps. Team roles are checked from the database on each request, because roles can change while a token is still valid.
- The GitHub OAuth token is used once and is **not stored**.
- Signing in does not grant repository access. Repository access will be a separate GitHub App step.

### Quick test without GitHub

1. Open http://localhost:8000/docs
2. Call `POST /auth/dev-login` with `{"github_user_id": "1001"}`
3. Call `GET /auth/me`. You should see Alice.

The cookie is set automatically. In Swagger you can also paste the returned `access_token` into **Authorize**.

---

## For the frontend team (Next.js)

- API base URL: `http://localhost:8000`
- Login: a normal link (full page navigation, not `fetch`) to `http://localhost:8000/auth/github/login`
- After login the user lands on `{FRONTEND_URL}/dashboard`; after a failed login on `{FRONTEND_URL}/login?error=github_failed`
- All API calls must use `credentials: "include"` so the browser sends the cookie
- A `401` from `/auth/me` means "not logged in"
- Use `localhost` everywhere. Do not mix `localhost` and `127.0.0.1`, because cookies are tied to the host name
- `FRONTEND_URL` must match the frontend origin exactly (protocol, host, port, no trailing slash), otherwise the browser reports a CORS error

```tsx
const API = process.env.NEXT_PUBLIC_API_URL; // http://localhost:8000

export const login = () => { window.location.href = `${API}/auth/github/login`; };

export async function getMe() {
  const res = await fetch(`${API}/auth/me`, { credentials: "include" });
  return res.status === 401 ? null : res.json();
}

export async function logout() {
  await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" });
}
```

In server components, forward the `access_token` cookie manually when calling the API.

---

## Running the tests

Tests use a separate PostgreSQL database so development data is never touched.

```bash
# one time
docker exec -it cloudpilot-db psql -U cloudpilot -c "CREATE DATABASE cloudpilot_test;"

# run
pytest -v
pytest tests/test_security.py     # fast tests, no database needed
pytest -k callback                # only tests with "callback" in the name
```

The suite covers JWT creation and rejection (tampered, expired, wrong secret, `alg: none`), user creation on first login, the GitHub callback flow with a fake GitHub client, cookie behavior, logout, and CORS.

---

## Database design (summary)

The full design has about 28 tables across these domains: Identity, Subscription, Project, Source Control, Analysis, Architecture, AWS, Deployment, AI, Monitoring, Incident/Healing, Cost, and Audit. It is built in phases, one Alembic migration per phase.

Key rules:

- History is preserved. A deployment references the exact commit and the exact architecture version it used.
- Each deployment has ordered steps, so the step that failed and its error can be identified.
- Flexible AI and architecture data is stored as `JSONB` instead of one table per AWS service.
- Status fields use `VARCHAR` plus `CHECK` constraints instead of native PostgreSQL enums, which are hard to change in Alembic.
- Foreign keys use `ON DELETE RESTRICT`. Projects are archived, not deleted.
- Prometheus time-series data and AWS secrets are never stored in PostgreSQL.
- AWS access will use a customer-created IAM role with an External ID and STS `AssumeRole`. Team members do not need IAM users.

Currently implemented: `users`, `teams`, `team_members`, `plans`, `subscriptions`, `projects`, `repositories`, `branches`, `commits`.

---

## Common problems

| Symptom | Cause / fix |
|---|---|
| `ValidationError ... Field required` at startup | A variable is missing in `.env`, or uvicorn was started outside `backend/` |
| `connection refused` | Docker is not running. Run `docker compose up -d` |
| Alembic generates an empty migration (`pass`) | `alembic/env.py` is missing `import app.models` or `target_metadata = Base.metadata`, or `models/__init__.py` does not import every model |
| `ModuleNotFoundError: No module named 'jwt'` | Install `pyjwt` (not `jwt`) |
| `400` or redirect to `/login?error=github_failed` after approving on GitHub | State cookie lost (mixed `localhost` and `127.0.0.1`), wrong client secret, or the callback URL in the GitHub app differs from `GITHUB_REDIRECT_URI` |
| CORS error in the browser | `FRONTEND_URL` does not match the frontend origin exactly. Restart uvicorn after changing `.env` |
| `/auth/me` is always 401 from the frontend | Missing `credentials: "include"` |
| Cookie not stored | `ENVIRONMENT` is not `development`, so the cookie is `Secure` and rejected over plain `http` |

---

## Security notes

- Never commit `.env`, secrets, or tokens. Never log them.
- `dev-login` exists only for development and is disabled when `ENVIRONMENT` is not `development`.
- The JWT is stored in an HttpOnly cookie, so JavaScript (and XSS) cannot read it. `SameSite=Lax` gives basic CSRF protection; before production, also reject state-changing requests with an unexpected `Origin` header.
- In production the frontend and API must share a parent domain (for example `app.example.com` and `api.example.com`) so the cookie is not treated as third-party.
- There is no refresh token yet. Tokens expire after 30 minutes and the user signs in again.

---

## Roadmap

1. **Phase 1 (in progress):** backend foundation, authentication, repository integration, basic analysis and architecture proposal, data model.
2. **Phase 2:** architecture editing, validation, cost estimation, Terraform generation, controlled deployment with approval, deployment history, conversational assistant.
3. **Phase 3:** monitoring, failure diagnosis, policy-based self-healing.
4. **Phase 4:** evaluation and research (analysis accuracy, deployment success rate, cost-estimate accuracy, comparison with a manual baseline).

Next implementation step: on first login, create a personal team, an `OWNER` membership, and a Free subscription in one transaction, then add team role checks and the `projects` module.
