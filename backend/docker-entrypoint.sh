#!/bin/sh
set -e

# Only the API container migrates and seeds (RUN_MIGRATIONS=false for the worker), so two
# containers never run Alembic at the same time.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "==> Applying database migrations..."
    alembic upgrade head

    # Seed initial plans and demo data if SEED_DEV_DATA flag is set
    if [ "$SEED_DEV_DATA" = "true" ] || [ "$SEED_DEV_DATA" = "1" ]; then
        echo "==> Seeding development and reference data..."
        python -m app.db.seed
    fi
fi

echo "==> Starting process: $@"
exec "$@"
