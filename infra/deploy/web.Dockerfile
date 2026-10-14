# Production web server: builds the Vue app and serves it with Caddy, which
# also terminates HTTPS and proxies the API. Build context: the repo root.
FROM node:22-slim AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
# --legacy-peer-deps: vue-router 5 declares an optional peer on Vite 7/8 while
# this project pins Vite 6; strict resolution refuses the lockfile over it.
RUN npm ci --legacy-peer-deps
COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine
COPY infra/deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv/app
