# AI-Native ERP Platform -- dev workflow shortcuts.
#
# Run each service in its own terminal (`make backend`, `make frontend`,
# `make tunnel`) rather than relying on `make dev` to background everything
# in one shell -- more reliable on Windows/Git Bash, and matches how this
# project has actually been run day to day. `make dev` is still provided as
# a best-effort convenience for a single terminal.

SHELL := /bin/sh

BACKEND_DIR := backend
FRONTEND_DIR := frontend
PYTHON := $(BACKEND_DIR)/.venv/Scripts/python.exe

# Podman containers backing local Postgres/Redis (shared with the
# journalist_app project on this machine -- see docs/notes.md / memory).
# They don't auto-start on boot/PC restart; `make db-up` brings them back.
DB_CONTAINER := journalist-app_postgres_1
REDIS_CONTAINER := journalist-app_redis_1

# cloudflared quick-tunnel port (scripts/tunnel.mjs) -- override with
# `make tunnel TUNNEL_PORT=...`.
TUNNEL_PORT := 5173

BACKEND_TEST_APPS := apps.core apps.inventory apps.purchasing apps.sales_crm apps.manufacturing apps.hr_payroll apps.ai_core

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install backend (pip) + frontend (npm) dependencies
	cd $(BACKEND_DIR) && ./.venv/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt
	cd $(FRONTEND_DIR) && npm install

.PHONY: db-up
db-up: ## Start the Postgres/Redis podman containers (see memory/dev_db_containers.md)
	podman start $(DB_CONTAINER) $(REDIS_CONTAINER)

.PHONY: db-down
db-down: ## Stop the Postgres/Redis podman containers
	podman stop $(DB_CONTAINER) $(REDIS_CONTAINER)

.PHONY: migrate
migrate: ## Apply Django migrations to every tenant schema
	cd $(BACKEND_DIR) && ./.venv/Scripts/python.exe manage.py migrate_schemas

.PHONY: backend
backend: ## Run the Django dev server on :8000
	cd $(BACKEND_DIR) && ./.venv/Scripts/python.exe manage.py runserver 0.0.0.0:8000

.PHONY: frontend
frontend: ## Run the Vite dev server on :5173
	cd $(FRONTEND_DIR) && npm run dev

.PHONY: tunnel
tunnel: ## Expose the frontend dev server via a Cloudflare quick tunnel (auto-restarts; prints the *.trycloudflare.com URL; requires `cloudflared` on PATH)
	TUNNEL_PORT=$(TUNNEL_PORT) node scripts/tunnel.mjs

.PHONY: dev
dev: db-up ## Best-effort: run backend + frontend + tunnel together in one terminal (Ctrl+C stops all)
	@trap 'kill 0' EXIT INT TERM; \
	( $(MAKE) backend ) & \
	( $(MAKE) frontend ) & \
	( $(MAKE) tunnel ) & \
	wait

.PHONY: test
test: ## Run the backend test suite
	cd $(BACKEND_DIR) && ./.venv/Scripts/python.exe manage.py test $(BACKEND_TEST_APPS) --noinput

.PHONY: build
build: ## Type-check + build the frontend for production
	cd $(FRONTEND_DIR) && npm run build
