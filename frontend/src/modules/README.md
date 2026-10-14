# Package modules

Each Django package app (`backend/apps/<package>/`) gets a matching folder here,
per `docs/technical.md` §10.1 — e.g. `purchasing/`, `inventory/`.

## Every module is a plugin

A module exposes its screens through a `plugin.ts` manifest (see
`src/plugins/types.ts`): its key, the subscription package that licenses it,
and the pages it adds to the left menu. Core's own plugins are declared the
same way in `src/core/plugins.ts`.

`src/plugins/registry.ts` lists every manifest. The router's routes and the
sidebar's links are both generated from that list, so:

- **To add a page**, add it to a manifest's `pages`, with the `action` a user
  needs to be offered it (the `view` action of the resource the page is
  about, e.g. `invoice.view`). Don't touch the router or the sidebar.
- **To add a module**, write its `plugin.ts`, add it to the registry, and add
  the same key to `PLUGINS` in `backend/apps/plugins/registry.py` (plus
  `plugins.catalog.<key>` strings in both locale files).

Page components are always dynamic imports, so a tenant only downloads the
screens of plugins it has installed. A plugin is active for a tenant when its
package is in the subscription *and* the tenant hasn't removed it on the
Plugins page (`src/core/views/PluginsView.vue`). A page is offered to a user
when its plugin is active and they hold the page's action (`auth.can(...)`).

## Actions, permissions and the audit trail

What a user may do is a list of action codes (`invoice.create`,
`purchase_order.approve`) sent with the session (`auth.user.access`). The
codes come from the backend's action catalog, which is read off the API views
themselves: decorating a view with `@resource("key", "plugin")`
(`backend/apps/access/catalog.py`) is the whole integration. That one line
gives the endpoint its permission check, an audit-log entry for every write,
undo where it's safe, and makes it usable from the AI assistant -- nothing
else needs registering. Give the new resource a name in both locale files
under `access.resources.<key>` (and any new operation under
`access.operations.<name>`).

## Home-panel widgets

Widgets are registered on the backend by the app that owns the data, in that
app's `dashboard_widgets.py`, under the plugin's key. Each returns one of a
few payload kinds (stat, chart, table), which the renderers in
`src/core/dashboard/` already know how to draw — a new widget normally needs
no new frontend component, only its `widgets.catalog.<key>` strings.
