#!/bin/sh
# Container start for the production backend (infra/deploy/backend.Dockerfile).
set -e

# Bring every schema (shared + each tenant) up to date before serving, so a
# deploy that adds a migration can't serve requests against the old tables.
python manage.py migrate_schemas --noinput

# Into the volume the web server serves at /static/.
python manage.py collectstatic --noinput --clear >/dev/null

# Threads rather than more processes: requests to the AI assistant wait on
# the model for many seconds, and a thread waiting on the network costs
# almost nothing. The timeout covers the longest of those requests.
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 --threads 8 \
    --timeout 300 \
    --access-logfile - --error-logfile -
