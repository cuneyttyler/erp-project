# Migration Agent

Standalone, separately-signed executable that runs on a customer's own network
to extract data from an on-prem legacy ERP database (Logo/Netsis/Mikro) into an
encrypted export bundle, without requiring inbound access into the customer's
environment. See [`docs/technical.md`](../docs/technical.md) §9.2 for the full
design and [`docs/requirements.md`](../docs/requirements.md) §10 (`REQ-DATA-005`,
`REQ-DATA-015`) for the requirements it satisfies.

**Status:** not started — this is `development-plan.md` Phase 1 scope, gated on
the Phase 0 decision in `technical.md` §9.8 (build vs. partner for legacy schema
expertise). Nothing to run yet.
