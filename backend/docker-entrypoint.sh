#!/bin/sh
set -e

# Run Alembic migrations to ensure database is at latest head
echo "==> Applying database migrations..."
alembic upgrade head

# Seed initial plans and demo data if SEED_DEV_DATA flag is set
if [ "$SEED_DEV_DATA" = "true" ] || [ "$SEED_DEV_DATA" = "1" ]; then
    echo "==> Seeding development and reference data..."
    python -m app.db.seed
fi

echo "==> Starting process: $@"
exec "$@"
