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
        echo "==> Running every quality gate (scripts/check.sh)..."
        sh "$(dirname "$0")/check.sh" all
        ;;
    logs)
        docker compose logs -f
        ;;
    reset)
        echo "==> Resetting stack and wiping named volumes..."
        docker compose down --volumes --remove-orphans
        ;;
    *)
        echo "Usage: $0 {up|down|test|logs|reset}"
        exit 1
        ;;
esac
