.PHONY: up down test test-backend test-frontend e2e logs reset clean help

help:
	@echo "CloudPilot Stack Management"
	@echo "  make up          - Build and start full stack (db, localstack, backend, frontend)"
	@echo "  make down        - Stop all containers"
	@echo "  make test        - Run backend and frontend test suites in containers"
	@echo "  make test-backend- Run backend test suite with coverage"
	@echo "  make test-frontend- Run frontend vitest suite"
	@echo "  make e2e         - Run Playwright end-to-end tests"
	@echo "  make logs        - Tail container logs"
	@echo "  make reset       - Tear down containers and delete all data volumes"

up:
	docker compose up --build -d

down:
	docker compose down

test: test-backend test-frontend

test-backend:
	docker compose run --rm backend-tests

test-frontend:
	docker compose run --rm frontend pnpm test

e2e:
	docker compose run --rm frontend pnpm test:e2e

logs:
	docker compose logs -f

reset:
	docker compose down --volumes --remove-orphans
