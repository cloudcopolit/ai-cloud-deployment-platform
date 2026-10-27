# CloudPilot reference app

A minimal FastAPI + PostgreSQL service used to test CloudPilot's container-postgres archetype
end to end. `GET /health` runs a real database query. Configuration: `DATABASE_URL`, or
`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`; `PORT` (default 8000).

```sh
docker build -t cloudpilot-reference-app examples/reference-app
```
