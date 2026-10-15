# Docker Compose environments

CloudPilot runs the implemented services (PostgreSQL, the FastAPI backend, and
the Next.js frontend) with Docker Compose. A shared base file is combined with
one overlay per environment:

| File | Purpose |
|---|---|
| [`docker-compose.yml`](../docker-compose.yml) | Shared base: services, health checks, dependency order. Not runnable on its own. |
| [`docker-compose.dev.yml`](../docker-compose.dev.yml) | Development: source mounts, hot reload, seed data, published ports. |
| [`docker-compose.test.yml`](../docker-compose.test.yml) | Testing: isolated project with an in-memory database that runs the test suites. |
| [`docker-compose.prod.yml`](../docker-compose.prod.yml) | Production: no mounts or dev tools, read-only containers, secrets supplied externally. |

The AI layer and Terraform have no runnable services yet, so they are not part
of these files. Add them here when their runtime requirements exist.

Requirements: Docker with Compose v2.24 or newer.

## Services

| Service | Image | Depends on | Health check |
|---|---|---|---|
| `db` | `postgres:16` (pinned by digest) | — | `pg_isready` |
| `migrate` | `backend/Dockerfile` (`runtime`) | `db` healthy | One-off: runs `alembic upgrade head` (plus the seed in development) and exits |
| `backend` | `backend/Dockerfile` (`runtime`) | `migrate` completed successfully | `GET /health/db` (checks the database connection) |
| `frontend` | `frontend/Dockerfile` (`runtime`; `dev` in development) | `backend` healthy | `GET /login` |

Both application images run as a non-root user. The frontend calls the API
server-side through the Compose network (`API_INTERNAL_URL=http://backend:8000`);
the browser uses `PUBLIC_API_URL`.

## Configuration

Compose reads variables from the shell or from an env file. The base file has
**no defaults for required values**, so Compose refuses to start when one is
missing instead of falling back to an insecure value.

| Variable | Required | Used by | Notes |
|---|---|---|---|
| `ENVIRONMENT` | yes | backend | `development` enables `/auth/dev-login` and non-`Secure` cookies; use `production` everywhere else |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | yes | db, backend | Also build the backend's `DATABASE_URL`; URL-encode special characters in the password |
| `JWT_SECRET_KEY` | yes | backend | Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI` | yes | backend | From your GitHub OAuth App |
| `FRONTEND_URL` | yes | backend | Exact frontend origin (CORS and post-login redirect) |
| `PUBLIC_API_URL` | yes | frontend | API address as seen by the browser. Inlined into the frontend at **build** time, so rebuild after changing it |
| `DB_PORT`, `BACKEND_PORT`, `FRONTEND_PORT` | no | dev, prod | Published ports (defaults 5432, 8000, 3000; the database is published only in development) |
| `BIND_ADDRESS` | no | prod | Host address for published ports (default `127.0.0.1`) |

[`.env.example`](../.env.example) holds **local-only placeholder values** for
development and testing. Never use it, or values copied from it, in production.

## Development

```bash
cp .env.example .env    # optional: add real GitHub OAuth values for GitHub sign-in
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

- Frontend: <http://localhost:3000> · API: <http://localhost:8000/docs> · PostgreSQL: `localhost:5432`
- `migrate` applies migrations and the idempotent seed, so `POST /auth/dev-login`
  with `{"github_user_id": "1001"}` works immediately (sign-in through GitHub
  needs real OAuth values).
- `backend/app` and `frontend/` are mounted into the containers; edits reload
  automatically (polling is enabled so this also works on Docker Desktop).
- After changing dependencies (`requirements.txt`, `package.json`), rebuild
  with `--build`.
- Stop with `docker compose -f docker-compose.yml -f docker-compose.dev.yml down`;
  add `--volumes` to delete the development database.

`backend/db.yml` still starts only the database for running the backend
directly on your machine (see the [backend README](../backend/README.md)). It
uses the same port, so run one or the other.

## Testing

The testing overlay is a separate Compose project (`cloudpilot-test`) whose
database lives in memory (`tmpfs`), so nothing persists between runs and it
never touches development data. The application services are disabled
(profile `stack`); only the test runners start.

```bash
T="docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.example"
$T run --rm --build backend-tests    # pytest + coverage against PostgreSQL 16
$T run --rm --build frontend-tests   # Vitest
$T down --volumes                    # cleanup: removes the test database and network
```

`backend-tests` runs `pytest --cov` with the same configuration and 90%
coverage gate as CI. Exit codes are passed through, so these commands can be
used in scripts.

## Production

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file /etc/cloudpilot/production.env up -d --build
```

What the production overlay guarantees:

- No source mounts, no hot reload, no seed data, and `ENVIRONMENT` must be set
  explicitly (set it to `production`; `/auth/dev-login` then returns 404).
- `backend`, `frontend`, and `migrate` run read-only, as non-root users, with
  all Linux capabilities dropped and `no-new-privileges`.
- The database is **not** published. The frontend and API are published on
  `127.0.0.1` only, unless you set `BIND_ADDRESS`.
- Containers restart automatically, and logs are rotated (3 × 10 MB).

What you must provide:

- **Secrets, from outside the repository.** Use an env file with restricted
  permissions (for example `chmod 600 /etc/cloudpilot/production.env`) or your
  platform's secret injection into the environment. Generate fresh values;
  never reuse `.env.example`.
- **TLS.** With `ENVIRONMENT=production`, auth cookies are `Secure`, so put a
  TLS-terminating reverse proxy in front of the frontend and API. Set
  `FRONTEND_URL`, `PUBLIC_API_URL`, and `GITHUB_REDIRECT_URI` to the public
  `https://` addresses.
- **Backups** of the `db-data` volume.

This is a single-host configuration. Cloud deployment (AWS, Terraform) is
planned separately and is not part of these files.

## Validation in CI

The `Infrastructure checks` job validates every Compose file on each pull
request: each `docker-compose.<env>.yml` overlay is merged with
`docker-compose.yml` and checked with `docker compose config`, using
`.env.example` for placeholder values. Hadolint and Trivy scan both
Dockerfiles. CI does not build or start the images.
