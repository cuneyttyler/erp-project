# Package modules

Each Django package app (`backend/apps/<package>/`) gets a matching folder here,
per `docs/technical.md` §10.1 — e.g. `purchasing/`, `inventory/`. Routes for a
module are only registered in `src/router/index.ts` (and therefore only
downloaded by the browser) for tenants whose `active_packages` includes that
package.

Nothing lives here yet — the first package (Purchasing) lands in
`development-plan.md` Phase 1.
