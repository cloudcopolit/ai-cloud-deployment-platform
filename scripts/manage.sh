#!/bin/sh
set -e

ACTION="${1:-help}"

case "$ACTION" in
    up)
        echo "==> Starting CloudPilot stack in background..."
        docker compose up --build -d
        ;;
    down)
        echo "==> Stopping CloudPilot stack..."
        docker compose down
        ;;
    test)
        echo "==> Running backend test suite in Docker..."
        docker compose run --rm backend-tests
        echo "==> Running frontend test suite in Docker..."
        docker compose run --rm frontend pnpm test
        ;;
    e2e)
        echo "==> Running Playwright E2E tests in Docker..."
        docker compose run --rm frontend pnpm test:e2e
        ;;
    logs)
        docker compose logs -f
        ;;
    reset)
        echo "==> Resetting stack and wiping named volumes..."
        docker compose down --volumes --remove-orphans
        ;;
    *)
        echo "Usage: $0 {up|down|test|e2e|logs|reset}"
        exit 1
        ;;
esac
