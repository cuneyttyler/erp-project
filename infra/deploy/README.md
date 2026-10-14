# Production deployment

One small server running everything in Docker Compose:

| Service | What it is | Reachable from outside |
|---|---|---|
| `web` | Caddy: serves the built Vue app, proxies `/api/` and `/admin/` to the backend, obtains and renews the HTTPS certificate | ports 80, 443 |
| `backend` | Django under gunicorn (`config.settings.prod`) | no |
| `postgres` | PostgreSQL 16 with pgvector; data in the `postgres_data` volume | no |
| `redis` | Redis 7 | no |

There is no Celery worker: nothing in the app queues background jobs yet. Add
one to `docker-compose.yml` when something does.

## Deploying a change

From the repo root, on a machine whose SSH key the server accepts:

```sh
infra/deploy/deploy.sh root@<server>
```

It uploads the working tree (committed or not), rebuilds the images on the
server and restarts what changed. The backend applies migrations to every
schema before it starts serving. The database and certificates live in Docker
volumes and are untouched.

## Configuration

`/opt/erp/infra/deploy/.env` on the server (never in git, never uploaded by the
deploy script):

| Variable | Meaning |
|---|---|
| `SITE_ADDRESS` | Public hostname. Caddy gets a certificate for it. |
| `DJANGO_ALLOWED_HOSTS` | Same hostname (comma-separated if several). |
| `CSRF_TRUSTED_ORIGINS` | `https://<hostname>`. |
| `DJANGO_SECRET_KEY` | Long random string. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Database credentials (also used to create the database on first start). |
| `AI_LLM_PROVIDER`, `MISTRAL_API_KEY` / `ANTHROPIC_API_KEY`, `AI_LLM_MODEL` | The assistant's model provider. |

After editing it: `docker compose up -d` in `/opt/erp/infra/deploy`.

## First-time setup of a server

1. Ubuntu with Docker and the compose plugin (`apt install docker.io docker-compose-v2`), ports 22/80/443 open.
2. Create `/opt/erp/infra/deploy/.env` as above.
3. Run `infra/deploy/deploy.sh root@<server>`.
4. Create the first organization, its admin user, company and chart of accounts:

   ```sh
   cd /opt/erp/infra/deploy
   docker compose exec -e BOOTSTRAP_ADMIN_PASSWORD='<password>' backend \
       python manage.py bootstrap_tenant --schema main --name "<Company name>" --domain <hostname>
   ```

   It's idempotent; re-running adds only what's missing and never resets a password.

## Using your own domain

Point an A record at the server, then on the server set `SITE_ADDRESS`,
`DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` to the new name, run
`docker compose up -d`, and route the name to the tenant:

```sh
docker compose exec backend python manage.py bootstrap_tenant --schema main --name "<Company name>" --domain <new hostname>
```

## Operating it

```sh
cd /opt/erp/infra/deploy
docker compose ps                    # what's running
docker compose logs -f backend       # application log
docker compose exec backend python manage.py shell
docker compose exec postgres pg_dump -U erp erp_platform | gzip > backup.sql.gz   # manual backup
```

**There are no automatic backups.** Until there are, the `postgres_data` volume
on this one server is the only copy of the data.
