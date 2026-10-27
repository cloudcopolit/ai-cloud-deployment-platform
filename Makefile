# CloudPilot developer commands. The gates live in scripts/check.sh (POSIX sh, so they also
# run where `make` is not installed, e.g. Git Bash on Windows).

COMPOSE := docker compose --env-file .env

.PHONY: help up down logs reset check check-backend check-ai check-frontend

help:
	@echo "make up              build and start the stack"
	@echo "make down            stop the stack (data kept)"
	@echo "make reset           stop the stack and delete its volumes"
	@echo "make check           every gate (scripts/check.sh)"
	@echo "make check-backend   ruff, mypy, pytest --cov incl. migration tests"
	@echo "make check-ai        ruff, mypy, pytest for ai/"
	@echo "make check-frontend  lint, typecheck, vitest, production build"

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

reset:
	$(COMPOSE) down --volumes --remove-orphans

check:
	sh scripts/check.sh all

check-backend:
	sh scripts/check.sh backend

check-ai:
	sh scripts/check.sh ai

check-frontend:
	sh scripts/check.sh frontend
