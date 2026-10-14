#!/bin/sh
# Ships the working tree to the server and (re)builds the stack there.
#
#   infra/deploy/deploy.sh root@<server>
#
# Run from the repo root. The server needs Docker with the compose plugin and
# an /opt/erp/infra/deploy/.env (see README.md) -- that file is never
# uploaded or overwritten by this script. Whatever is in your working tree is
# what gets deployed, committed or not.
set -eu

HOST="${1:?usage: infra/deploy/deploy.sh user@host}"
SSH="ssh -o BatchMode=yes ${SSH_OPTS:-}"

echo "==> Uploading code to $HOST"
tar czf - \
    --exclude='node_modules' --exclude='.venv' --exclude='__pycache__' \
    --exclude='dist' --exclude='staticfiles' --exclude='.env' --exclude='.env.*' \
    backend frontend infra .dockerignore |
    $SSH "$HOST" '
        set -e
        mkdir -p /opt/erp
        cd /opt/erp
        # Replace the code wholesale so a file deleted locally is gone there
        # too -- but keep the server-side .env.
        [ -f infra/deploy/.env ] && cp infra/deploy/.env /tmp/erp.env.keep
        rm -rf backend frontend infra
        tar xzf -
        [ -f /tmp/erp.env.keep ] && mv /tmp/erp.env.keep infra/deploy/.env
        test -f infra/deploy/.env || { echo "Missing /opt/erp/infra/deploy/.env" >&2; exit 1; }
        chmod 600 infra/deploy/.env
    '

echo "==> Building and starting"
$SSH "$HOST" 'cd /opt/erp/infra/deploy && docker compose up -d --build --remove-orphans && docker image prune -f >/dev/null'

echo "==> Status"
$SSH "$HOST" 'cd /opt/erp/infra/deploy && docker compose ps'
