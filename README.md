# AI-Native ERP Platform

Product/architecture background lives in [`docs/`](docs/):
[`product.md`](docs/product.md) (vision & market), [`requirements.md`](docs/requirements.md)
(what it must do), [`development-plan.md`](docs/development-plan.md) (build phases), and
[`technical.md`](docs/technical.md) (how it's built — Django + Vue). This README is
just "how do I run it locally"; the *why* behind every choice below is in those docs.

## Status

Phase 0 foundation (`development-plan.md` §3): repo scaffold, multi-tenant Django
backend skeleton, Vue app shell with a placeholder AI panel. No package modules
(Purchasing, Inventory, ...) exist yet — that's Phase 1.

## Stack

- **Backend**: Django 5 + Django REST Framework, schema-per-tenant multi-tenancy
  via `django-tenants` (technical.md §3), Celery + Redis for async jobs, Channels
  for the AI chat stream.
- **Frontend**: Vue 3 + TypeScript + Vite, Pinia, Vue Router, vue-i18n (Turkish
  default, English fully supported), Tailwind CSS v4.
- **Database**: PostgreSQL 16.

## Running locally

### Option A — Docker Compose (closest to how it'll actually run)

```bash
docker compose up --build
```

- Backend: http://localhost:8000 (admin at `/admin/`, API docs at `/api/docs/`)
- Frontend: http://localhost:5173

First time only, migrate the shared/public schema, then create your first tenant
(see `docs/technical.md` §3 for what schema-per-tenant means in practice — creating
a `Client` auto-creates its own Postgres schema and runs the tenant-app migrations
into it):

```bash
docker compose exec backend python manage.py migrate_schemas --shared
docker compose exec backend python manage.py create_tenant   # prompts for schema_name, name, domain_url, ...
docker compose exec backend python manage.py create_tenant_superuser --schema=<schema_name>
```

### Option B — Native (faster iteration while there's little to containerize)

**Backend:**

```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env             # then point DB_HOST/REDIS_URL at your local Postgres/Redis
python manage.py migrate_schemas --shared
python manage.py runserver
```

Requires a local PostgreSQL 16 (pgvector-enabled) and Redis — easiest to still get
those two from Compose (`docker compose up postgres redis`) even if you run
Django/Vite natively. If you already run a shared local Postgres instance for other
projects, you don't need a second server: just create an isolated role + database
on it (`CREATE ROLE erp WITH LOGIN PASSWORD 'erp'; CREATE DATABASE erp_platform
OWNER erp;`, then `CREATE EXTENSION vector;` while connected to `erp_platform`) and
point `backend/.env` at it. This is what local dev for this project actually uses
right now — see `backend/.env` (git-ignored) for the real values.

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api/*` to `http://localhost:8000` in dev (see `frontend/vite.config.ts`),
so no CORS configuration is needed for local work.

## Repository layout

Mirrors `docs/technical.md` §17:

```
/backend            Django project — one app per package (technical.md §4)
/frontend            Vue 3 SPA — one module per package (technical.md §10.1)
/infra                Docker/IaC (grows from Phase 2 onward)
/migration-agent      Standalone legacy-DB export tool (technical.md §9.2) — empty until Phase 1
/docs                 product.md, requirements.md, development-plan.md, technical.md
```

## Conventions

- Every non-trivial architectural choice traces back to a `REQ-*` ID in
  `requirements.md` — look for the code comment before assuming something is
  arbitrary.
- Package apps must not import each other's internals (`technical.md` §4) — a
  tenant without a package should never even run that package's code.
