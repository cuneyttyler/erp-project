# Technical Architecture — AI-Native ERP Platform (Django / Vue)

**Status:** Draft v1 — derived from [`requirements.md`](./requirements.md) and [`development-plan.md`](./development-plan.md)
**Last updated:** 2026-07-31
**Stack decision:** Django (backend/API) + Vue (frontend SPA), as directed.
**Purpose:** This document specifies *how* the product is built. Every architectural choice below is made to satisfy specific `REQ-*` items from `requirements.md` — cited inline — and is sequenced to match `development-plan.md`'s phases. Where a decision is genuinely open, it's marked **[DECISION NEEDED]** rather than silently assumed.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Vue 3 SPA (TypeScript)                        │
│  App shell · lazy-loaded package modules · persistent AI side-panel  │
│  Pinia stores · vue-i18n (TR/EN) · design-system component library   │
└───────────────┬───────────────────────────────────┬─────────────────┘
                │ REST (DRF, JSON) + OpenAPI          │ SSE / WebSocket
                │                                     │ (AI chat stream)
┌───────────────▼───────────────────────────────────▼─────────────────┐
│                     Django API Layer (per-tenant scoped)              │
│  ┌───────────┐ ┌───────────┐ ┌────────────┐ ┌──────────────────────┐│
│  │   core    │ │ purchasing│ │  inventory │ │  ai_core (chat,      ││
│  │ (GL/AR/AP/│ │           │ │            │ │  semantic layer,     ││
│  │ users/    │ │  ...other │ │            │ │  tool registry,      ││
│  │ perms)    │ │  package  │ │            │ │  agent orchestrator, ││
│  │           │ │  apps     │ │            │ │  audit log)          ││
│  └───────────┘ └───────────┘ └────────────┘ └──────────────────────┘│
│  ┌──────────────────────────┐ ┌─────────────────────────────────────┐│
│  │ compliance (localization │ │ integrations (GİB/özel entegratör,  ││
│  │ engine + Turkey adapter) │ │ banks, e-commerce, SMS/email, PSPs) ││
│  └──────────────────────────┘ └─────────────────────────────────────┘│
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ migration (import pipeline + per-source-system adapters:         ││
│  │ Logo, Mikro, generic DB/CSV — see §9)                            ││
│  └──────────────────────────────────────────────────────────────────┘│
└───────────────┬───────────────────────────┬───────────────────────────┘
                │                            │
      ┌─────────▼─────────┐        ┌─────────▼──────────┐
      │ PostgreSQL (+pgvector)│    │ Redis (cache, Celery │
      │ schema-per-tenant     │    │ broker, channel layer)│
      └───────────────────────┘    └───────────────────────┘
                │
      ┌─────────▼─────────┐        ┌────────────────────────┐
      │ Celery workers      │◄─────►│ Object storage (S3-    │
      │ (async jobs, AI,    │        │ compatible) — documents,│
      │ migration imports,  │        │ compliance filings, and │
      │ reports)            │        │ encrypted migration     │
      └─────────────────────┘        │ export bundles          │
                                      └────────────────────────┘
```

Key architectural commitments this diagram encodes:
- The AI layer (`ai_core`) is a first-class backend component alongside business modules, not a separate bolt-on service calling into the ERP from outside — satisfies `REQ-CORE-AI-004`'s requirement that AI never has broader access than the requesting user.
- `compliance` is its own app with a pluggable per-country adapter, not logic scattered across every module — satisfies `REQ-CORE-LOC-001`.
- `migration` mirrors that same pluggable-adapter pattern for legacy-system import (Logo, Mikro, generic) — satisfies `requirements.md` §10, detailed in §9 below.
- Every package is its own Django app with its own Vue lazy-loaded module, so a tenant who hasn't purchased a package never runs its code or downloads its frontend bundle.

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend language/framework | Python 3.12, Django 5.x | As directed; mature, batteries-included, excellent ORM for a data-heavy ERP domain |
| API layer | Django REST Framework (DRF) + `drf-spectacular` for OpenAPI schema | Industry-standard, satisfies `REQ-INT-007` public API requirement with auto-generated docs |
| Database | PostgreSQL 16 | Strong transactional guarantees (needed for double-entry GL), native JSON support, `pgvector` extension covers AI embedding storage without a separate vector DB in Phase 1 |
| Async/background jobs | Celery + Redis | Report generation, AI agent execution, compliance filing submission, scheduled agents (`REQ-AIAGENT-001`) |
| Real-time/streaming | Django Channels (ASGI) | Powers the AI chat panel's streamed responses (`REQ-NFR-PERF-004`) |
| Caching | Redis | Semantic-layer query result caching (latency mitigation, see §8.7) |
| Frontend framework | Vue 3 (Composition API) + TypeScript | As directed; TypeScript is non-negotiable for a domain this data-shape-heavy |
| Build tooling | Vite | Fast dev server, native code-splitting for the lazy-loaded package-module pattern |
| State management | Pinia | One store per package module, plus a global AI-conversation store |
| Routing | Vue Router, per-package route modules loaded only if the tenant owns that package | |
| i18n | `vue-i18n` (frontend), Django `i18n`/`gettext` (backend, for emails/PDFs) | Satisfies `REQ-NFR-I18N-001/002` |
| UI/design system | Headless component primitives (Radix-Vue or equivalent) + Tailwind CSS, wrapped in an internal component library | Keeps design consistent across 10+ package modules built over 4 phases |
| LLM access | Provider-abstracted gateway (see §8.8) | Avoids hard lock-in to one model vendor; billing/metering needs usage accounting regardless of vendor |
| Vector store | `pgvector` (Phase 1–2); evaluate a dedicated vector DB only if scale demands it (Phase 3+) | Avoids introducing a second database technology before it's proven necessary |
| Object storage | S3-compatible (AWS S3 or a Turkey-region-compatible equivalent) | Document attachments (`REQ-CORE-DOC-001`), compliance filing archives (`REQ-LOC-TR-008`), encrypted migration export bundles (`REQ-DATA-014`) |
| Search (non-AI, e.g. product/customer lookup) | PostgreSQL full-text search initially; reconsider Elasticsearch/OpenSearch only if scale demands it | Avoid a second search stack until proven necessary |
| Migration Agent (local export tool) | Small standalone Python executable (packaged with PyInstaller or equivalent), run by the customer/reseller against their own on-prem database | Extracts legacy data without requiring inbound network access into the customer's environment — see §9.3 |
| CI/CD | GitHub Actions (or equivalent) | Automated test + deploy pipeline |
| Containers/orchestration | Docker; Kubernetes from Phase 2 onward (Docker Compose sufficient for Phase 0/1 scale) | Avoids over-engineering infra before there's tenant load to justify it |
| Observability | Sentry (errors), Prometheus + Grafana (metrics), structured JSON logging | Includes AI-specific dashboards: latency, cost per query, action-approval rates |

---

## 3. Multi-Tenancy Strategy

**[DECISION NEEDED — recommendation below]**

Two realistic options for a Django/Postgres ERP:

| Approach | Description | Pros | Cons |
|---|---|---|---|
| **Schema-per-tenant** (`django-tenants` / `django-tenant-schemas`) | Each tenant gets its own Postgres schema; shared tables (billing, tenant registry) live in a `public` schema | Strong data isolation (defense-in-depth for `REQ-NFR-SEC-006`); simpler backup/restore per tenant; easier to reason about KVKK data-subject deletion requests (`REQ-NFR-SEC-004`) — drop a schema, done | Schema count grows with tenant count; cross-tenant reporting (e.g., our own product analytics) is harder; migrations must run per-schema |
| **Shared schema + `tenant_id` column** (row-level, enforced via Django manager + Postgres Row-Level Security) | One set of tables, every row tagged with `tenant_id`, RLS policies enforce isolation at the DB level | Simpler migrations (one pass); easier cross-tenant analytics for us | A single missed `tenant_id` filter or RLS policy bug is a cross-tenant data leak — much higher blast radius for the exact failure mode `REQ-NFR-SEC-006` is written to prevent |

**Recommendation: schema-per-tenant**, specifically because this product's core trust proposition is financial-data integrity and Turkish regulatory compliance — the isolation guarantee is worth the added operational complexity, and it directly reduces the AI-specific risk called out in `product.md` §5.3 (permission/data-leakage failures like EchoLeak/SearchLeak traced back to insufficiently isolated retrieval). Row-level security can still be layered *within* a tenant's schema for role/field-level permission enforcement (`REQ-CORE-USR-002/003`) — the two approaches aren't mutually exclusive at different levels.

For very small Starter-tier tenants, evaluate schema pooling/connection management carefully (Postgres has practical limits on schema count per instance before connection overhead matters) — this is an infrastructure scaling concern for `development-plan.md` Phase 1 exit, not a Phase 0 blocker.

---

## 4. Django App / Module Structure

One Django app per product package, mirroring `product.md` §6 and `requirements.md` §5 exactly — this 1:1 mapping is deliberate so "is this a Core or Package feature" is never ambiguous in the codebase.

```
apps/
  core/                # Tenant, User, Role, Permission, GL, COA, AR/AP, Audit, Notifications, Documents
  compliance/           # Localization framework + country adapters (turkey/ subpackage first)
  purchasing/
  inventory/
  manufacturing/
  sales_crm/
  hr_payroll/
  projects/
  pos/
  ecommerce/
  bi_analytics/
  ai_core/              # Chat, semantic layer registry, tool registry, agent orchestrator, golden-query store, AI audit log
  integrations/         # GİB/özel entegratör client, bank feeds, payment gateways, e-commerce marketplace clients, email/SMS
  migration/            # Import pipeline + per-source-system adapters (logo/, mikro/, generic/) — see §9
```

Each package app follows the same internal shape:

```
apps/<package>/
  models.py            # or models/ package if large
  serializers.py
  views.py / viewsets.py
  permissions.py       # DRF permission classes, tenant + role + field-level checks
  signals.py           # e.g., PO received -> AP bill draft created
  tasks.py             # Celery tasks (async/scheduled work for this package)
  ai_tools.py           # This package's AI-callable tool definitions (see §8.4)
  tests/
```

**Cross-app rule:** packages may depend on `core` and `compliance`, but must not import directly from each other's internals — cross-package interactions (e.g., Sales creating an Inventory stock reservation) go through each package's public service layer / signals, never reaching into another app's models directly. This keeps the "a tenant without Package X never even runs Package X's code" guarantee (`product.md` §6.2) enforceable, and keeps packages independently testable and independently sellable as the codebase grows across four phases.

---

## 5. Core Data Model

Not an exhaustive schema — the entities whose shape has the widest blast radius if gotten wrong, worth deciding carefully in Phase 0 (`development-plan.md` §3).

| Entity | Key fields | Notes |
|---|---|---|
| `Tenant` | id, name, subscription_tier, schema_name, locale, active_packages[] | Lives in the shared/public schema |
| `User` | id, tenant (FK, nullable for the external-accountant case), email, mfa_enabled | Supports `REQ-CORE-USR-006` external-accountant cross-tenant access via a separate `TenantAccess` join model, not a `tenant` FK alone |
| `Role` / `Permission` | name, granted_actions (view/create/edit/delete/approve/export) per module | Backs `REQ-CORE-USR-002/003` |
| `Account` (COA) | code, name, type, parent (self-FK for hierarchy), entity (FK) | Supports Turkish Tekdüzen Hesap Planı structure out of the box |
| `JournalEntry` / `JournalLine` | date, memo, source_document (generic FK), lines[] (account, debit, credit) | Immutable once posted (`REQ-CORE-GL-008`); draft/posted state machine |
| `Party` (Customer/Vendor, unified) | tax_id (VKN/TCKN, validated per `REQ-DATA-003`), name, payment_terms | Unified base to avoid duplicating similar entities between AR and AP |
| `Invoice` (AR) / `Bill` (AP) | party, lines[], status, linked e-Fatura/e-Arşiv document ref | Status machine backs `REQ-CORE-AR-002` |
| `Item` (Product/Service) | sku, uom, cost_method, tracked_by (none/lot/serial) | Shared by Inventory, Purchasing, Sales, Manufacturing |
| `Warehouse` / `StockMove` | location, item, quantity, move_type (receipt/transfer/pick/adjustment) | Backs `REQ-INV-002/003` |
| `PurchaseOrder` / `SalesOrder` | party, lines[], approval_state | Approval workflow per `REQ-PUR-002` |
| `BOM` / `WorkOrder` | item, components[], routing, status | Manufacturing (Phase 2) |
| `Employee` / `PayrollRun` | personal info (KVKK-sensitive, field-level restricted per `REQ-CORE-USR-003`), SGK registration data | Phase 2 |
| `Project` / `Task` / `TimeEntry` | budget, actuals rollup | Phase 3 (per current plan, though listed in requirements as its own package) |
| `AuditLogEntry` | actor (user or "AI:<user>"), action, target (generic FK), before/after diff, timestamp | Append-only; enforced at the DB permission level, not just application logic (`REQ-CORE-AUDIT-002`) |
| `AIActionLog` | user, prompt, retrieved_context_refs[], tool_calls[], model_used, approval_state, approved_by | Satisfies `REQ-CORE-AUDIT-003`; see §8.6 |
| `ComplianceFiling` | filing_type (e-Fatura/e-Defter/etc.), period, status, raw_payload_ref, gib_response_ref | One unified model across all filing types, per-type validators live in `compliance/turkey/` |
| `MigrationJob` | tenant, source_system (logo/mikro/generic), status (uploaded/mapping/dry_run/committed/rolled_back), raw_bundle_ref | One per customer migration attempt; see §9 |
| `MigrationMappingRule` | migration_job (FK), source_field, target_field/account, confidence_score, confirmed_by | AI-proposed, human-confirmed mapping (`REQ-DATA-008`); never auto-applied without confirmation |
| `MigrationRecordLog` | migration_job (FK), source_record_ref, target_record_ref (nullable), status (imported/skipped/error), reason | Per-record outcome, backs the dry-run preview (`REQ-DATA-009`) and progress dashboard (`REQ-DATA-012`) |

---

## 6. API Design

- **Versioned REST API** under `/api/v1/`, per package (`/api/v1/purchasing/orders/`, `/api/v1/inventory/stock-moves/`, etc.) — satisfies `REQ-INT-007`.
- **DRF ViewSets + routers** per resource, with `drf-spectacular` generating the OpenAPI schema automatically — kept in sync with code by construction, not maintained by hand.
- **Filtering/pagination**: `django-filter` for query parameters, cursor pagination for large transactional lists (stock moves, journal lines) to keep `REQ-NFR-PERF-001/002` achievable at scale.
- **Permission classes**: every ViewSet composes a tenant-scope check + role/action check + (where relevant) field-level serializer restriction — the same permission classes are reused by the AI tool layer (§8.4), so there is exactly one place permission logic lives, never a second AI-specific path (directly satisfies `REQ-CORE-AI-004` / `REQ-AI-XCUT-002`).
- **AI chat/streaming endpoint** is the one deliberate exception to plain REST: a WebSocket (Django Channels) or Server-Sent-Events endpoint for the conversational panel, since a request/response REST call can't stream a token-by-token AI response (`REQ-NFR-PERF-004`).
- A GraphQL layer is **not** planned for the general API — REST is sufficient for CRUD-heavy ERP resources, and introducing a second query paradigm alongside the AI semantic layer (§8.2, which is its own purpose-built query interface) would add complexity without a clear win.

---

## 7. Turkey Compliance Integration Architecture

This is the highest-risk, highest-priority technical area per `development-plan.md` Phase 0/1.

### 7.1 Build vs. partner for GİB connectivity — **[DECISION NEEDED]**

| Option | Description | Tradeoff |
|---|---|---|
| **A. Become a certified özel entegratör** | Direct GİB integration, our own signing infrastructure (mali mühür), full control | Certification process has real cost/time/compliance overhead (security audits, GİB approval) before Phase 1 can even exit — directly threatens the Phase 1 timeline in `development-plan.md` §11 |
| **B. Integrate through an existing özel entegratör** (e.g., a partner offering an API/white-label layer — commercial vendors like Foriba/Sovos, İzibiz, Uyumsoft, Nesbilgi operate in this space) | We call their API for e-Fatura/e-Arşiv/e-Defter generation and GİB transmission; our compliance app becomes an adapter over their API rather than over GİB directly | Faster to a working Phase 1; recurring per-document/per-tenant cost from the partner; some loss of control over the exact filing pipeline |

**Recommendation:** Option B for Phase 1, revisit Option A only once the compliance workload/tenant volume justifies the fixed cost of direct certification. The `compliance/turkey/` adapter should be written against our own internal interface (`generate_e_invoice(invoice) -> FilingResult`) so that swapping the underlying implementation from "calls Partner X's API" to "calls GİB directly" later is an internal refactor, not a rewrite of every module that calls into compliance.

### 7.2 Adapter pattern

```
compliance/
  engine.py            # Country-agnostic interface: file(filing_type, payload) -> FilingResult
  turkey/
    e_fatura.py          # UBL-TR XML generation + signing + transmission (via chosen partner/direct)
    e_arsiv.py
    e_defter.py           # XBRL-GL + berat generation
    e_irsaliye.py
    e_mustahsil.py
    sgk_ebildirge.py
    kdv_ebeyanname.py
    validators.py         # VKN/TCKN checksum (REQ-DATA-003), threshold config (REQ-LOC-TR-001 etc.)
    thresholds.py         # Configurable, versioned threshold table -- NOT hardcoded, since GİB changes these ~annually (REQ-LOC-TR-009)
```

`thresholds.py` deserves special mention: every revenue/threshold number in `requirements.md` §6 must be a **data-driven, versioned configuration value** (with an effective-date range), never a hardcoded constant — this is the single most important implementation detail protecting against the recurring "GİB changed a threshold again" failure mode flagged throughout `product.md` and `development-plan.md`.

### 7.3 Filing pipeline
1. Triggering event (invoice posted, month-end, payroll run finalized) enqueues a Celery task.
2. Adapter generates the required document format, validates it against the current schema/threshold config.
3. Document is signed (digitally, per GİB requirements) and transmitted via the chosen path (§7.1).
4. `ComplianceFiling` record stores status, GİB/partner response reference, and the document itself in object storage (`REQ-LOC-TR-008` — 5-year retention).
5. Failure/retry handling with alerting — a failed e-Fatura transmission is a Sev-1 operational event, not a background job that silently retries forever.

---

## 8. AI Architecture (Detailed)

This section implements the principles from `product.md` §5 concretely, satisfying `requirements.md` §4.4 and §7.

### 8.1 Why not raw text-to-SQL
As established in `product.md`'s research, letting an LLM free-compose SQL over the full schema is not viable at enterprise accuracy levels (accuracy collapses ~91%→21% on realistic schemas). The architecture below exists specifically to avoid that failure mode.

### 8.2 Semantic layer (`ai_core/semantic/`)
- A registry of **named metrics and dimensions**, each backed by a Django ORM queryset or parameterized SQL template — e.g., `gross_margin`, `overdue_ap_balance`, `stock_on_hand` are defined once, centrally, and versioned.
- The LLM's job for a data question is: (1) identify which registered metric(s)/dimension(s) answer the question, (2) extract parameters (date range, entity, filters) from the user's natural language, (3) call the metric — it never writes ad hoc SQL itself.
- This directly prevents the "metric drift" failure mode (`product.md` §5.1) — every consumer (dashboards, reports, AI) computes "gross margin" via the same registered definition.
- Implemented as a Django app-level registry (`@register_metric` decorator pattern), not a separate service — keeps it in the same codebase/deploy unit as the models it queries, at least through Phase 3.

### 8.3 Read path (Q&A)
`User question → intent/metric matching (LLM call #1) → semantic layer executes deterministic query → LLM call #2 narrates the result in the user's language, with citations back to source records.`
Both LLM calls run through the same permission-scoped context as the requesting user (§8.5) — there is no elevated "AI service account."

### 8.4 Write path (actions) — tool-calling / MCP pattern
- Each package app exposes an `ai_tools.py` defining typed, schema-validated functions (e.g., `purchasing.create_po(vendor_id, lines, ...) -> PurchaseOrder`) — modeled on the Model Context Protocol (MCP) pattern now converged on industry-wide (`product.md` §5).
- Every tool function **re-runs the same DRF permission checks** the equivalent REST endpoint would use — the tool is a thin wrapper around the same service-layer call the API view uses, not a separate code path with its own (possibly weaker) authorization logic.
- Tools above a configurable risk/value threshold (`REQ-CORE-AI-010`) don't execute immediately — they create a `PendingApproval` record (durable, survives a server restart, unlike an in-memory flag) and notify the user; execution proceeds only on explicit confirmation.
- `django-fsm` (or an equivalent explicit state machine) models the `PendingApproval` lifecycle (`pending → approved → executed` / `pending → rejected`) rather than ad hoc boolean flags.

### 8.5 Permission enforcement
- The AI layer authenticates as the requesting user (their existing session/token), never as a privileged system account — this single decision is what makes `REQ-CORE-AI-004` and `REQ-AI-XCUT-002` structurally true rather than merely policy.
- Row/field-level restrictions (`REQ-CORE-USR-003`) apply identically whether the data is being rendered in the Vue UI or narrated by the AI — both paths go through the same serializer-level restrictions.
- Document/RAG retrieval (§8.7) is filtered by the same ACL metadata at query time, not filtered after a broad retrieval — directly addresses the EchoLeak/SearchLeak-style failure mode referenced in `product.md` §5.3.

### 8.6 Audit trail
- Every AI interaction — question or action — writes an `AIActionLog` row: the user's prompt, which metrics/tools were invoked and with what parameters, what was retrieved, the model used, and (for actions) the approval decision and approver.
- Append-only at the database permission level (a Postgres role with `INSERT`-only privilege on this table, no application code path issues `UPDATE`/`DELETE`).
- Exportable in a structured format to support both internal debugging and the EU AI Act-style audit obligations noted in `product.md` §5.

### 8.7 RAG for unstructured content
- Contracts, policies, and uploaded documents (`REQ-CORE-DOC-002`) are embedded and stored in `pgvector`, tagged with the same tenant-schema isolation as everything else (schema-per-tenant already solves cross-tenant leakage here for free).
- RAG retrieval is used to find *relevant unstructured context* (e.g., "what does our vendor contract say about late-delivery penalties") — it is explicitly **not** used to retrieve or compute financial figures, which always go through the semantic layer (§8.2) instead.

### 8.8 LLM provider abstraction & metering
- A thin gateway module (`ai_core/llm_gateway.py`) abstracts the actual model provider behind a stable internal interface, so the product isn't hard-locked to one vendor and can route different task types (fast intent-matching vs. deeper agentic reasoning) to different models/tiers as needed.
- Every call through the gateway records token/action usage against the tenant's metered "AI Action credits" (`REQ-CORE-AI-011`, billing model in `product.md` §7.2) — metering is a property of the gateway, not bolted on per call-site.
- **[DECISION NEEDED]**: primary LLM vendor selection is a commercial/legal decision (data-processing terms, EU/Turkey data-handling commitments matter given `REQ-NFR-SEC-004/005`) as much as a technical one — flagged for a dedicated decision outside this document, informed by the `claude-api` reference material already available to this team.

### 8.9 Golden-query library & feedback loop
- A `GoldenQuery` model stores verified natural-language ↔ metric/tool-call pairs, vector-searchable, used as few-shot grounding for the intent-matching step (§8.3).
- When a user corrects or rejects an AI-generated answer/action, that correction is captured and (after a human review step, not fully automatically) can be promoted into the golden-query set — a continuous accuracy-improvement loop, and the backbone of the automated AI regression testing referenced in `development-plan.md` §9.

### 8.10 Latency mitigation
- Redis-backed result caching for semantic-layer queries with a short TTL, since most "what's my cash position" style questions tolerate a few minutes of staleness.
- Celery-based pre-aggregation for expensive rollups (e.g., nightly materialized views for reporting-heavy metrics) rather than computing over raw transactional tables at question time.
- Target: streamed first-token within 3 seconds, full answer within 10 seconds for typical queries (`REQ-NFR-PERF-004`) — enforced via the AI evaluation harness (`development-plan.md` §9), not just aspirational.

---

## 9. Data Migration & Legacy System Integration Architecture

This section implements `product.md` §2 (pillar 6) and satisfies `requirements.md` §10 in full. It is treated with the same architectural seriousness as Turkey compliance (§7) — a rushed or bolted-on migration path undermines the exact "switching cost is Logo's real moat, not their product quality" thesis this platform is built around.

### 9.1 Architecture pattern: mirrors `compliance`'s adapter design

```
migration/
  engine.py             # source-agnostic interface: import_job(source_system, bundle) -> MigrationJob
  logo/
    schema_reader.py      # reads a Logo export/backup's known table structure (Tiger/GO/j-Platform/Netsis family)
    mapper.py              # proposes COA/master-data mapping (AI-assisted, see §9.5)
  mikro/
    schema_reader.py
    mapper.py
  generic/
    csv_reader.py          # REQ-DATA-001/007 fallback
    db_reader.py           # generic ODBC/SQL connection for undocumented sources
  validators.py           # VKN/TCKN checks (REQ-DATA-003), balance validation, duplicate detection
  reconciliation.py       # parallel-run comparison tooling (REQ-DATA-010)
```

Just as `compliance/` isolates country-specific filing logic behind one shared interface, `migration/` isolates source-system-specific extraction/mapping logic behind one shared pipeline — adding a new source system (a future accounting package, a different Netsis variant) means adding a new subpackage, not touching the pipeline itself.

### 9.2 Getting bytes out of an on-prem legacy database — the Migration Agent

Most Logo/Netsis/Mikro installs are on-premise (SQL Server, or Firebird for some older Netsis versions), with no exposed API and no realistic way to open inbound network access into a small business's environment. Two supported extraction paths:

1. **Migration Agent (primary path)**: a small, downloadable standalone executable (e.g., Python packaged with PyInstaller) that the customer or their IT/reseller runs locally, on the same network as the legacy database. It connects via ODBC/the database's native driver, extracts a defined set of tables (per the relevant `schema_reader.py`) into an encrypted, versioned export bundle, and the customer uploads that bundle through the platform's migration wizard. This needs no VPN/inbound tunnel into the customer's network — a real constraint for SMBs and a security liability we'd otherwise own — while still fully automating extraction rather than requiring manual re-entry.
2. **Raw backup upload (fallback path)**: many businesses already take periodic full database backups ("yedek alma") of their legacy system for their own disaster-recovery purposes. The platform accepts a raw backup file directly, processed server-side in an isolated, sandboxed job, for customers who can't or won't run a local agent tool.

### 9.3 Import pipeline stages

1. **Upload** — Migration Agent bundle, raw DB backup, or spreadsheet template (`REQ-DATA-001`).
2. **Source detection / adapter selection** — automatic where the format is unambiguous; explicit customer selection otherwise.
3. **Field/account mapping** — the relevant adapter's `mapper.py` proposes a mapping (§9.5); the customer/accountant reviews and confirms every entry (`REQ-DATA-008`) — never auto-applied for financially significant fields.
4. **Dry-run / validation** — `validators.py` runs the full import into a staging area within the tenant's own schema (§9.4), producing the preview report (`REQ-DATA-009`) without affecting any record the rest of the application can see.
5. **Human review & correction** — the customer resolves flagged errors/duplicates or explicitly accepts documented exceptions.
6. **Commit** — only on explicit confirmation are staged records promoted to live, application-visible data; this is the one meaningfully irreversible step (`REQ-DATA-013`).
7. **Post-migration reconciliation** — `reconciliation.py` compares key totals against the legacy system for the parallel-run window (`REQ-DATA-010`, §9.6).

### 9.4 Staging & rollback, using schema-per-tenant

Because each tenant already has an isolated schema (§3), a migration can be staged **inside the tenant's own schema** via an `is_migrated_draft` flag on imported records, rather than requiring a separate database or environment. Nothing staged is visible through the normal UI/API/AI layer until the commit step promotes it — enforced the same way any other visibility rule is enforced (§8.5), not as a migration-specific special case. A committed migration remains reversible within a defined window (e.g., before the tenant's first live GİB filing) — that window closes once statutory filings start depending on the imported data, since those filings aren't themselves reversible.

### 9.5 AI-assisted mapping

- Reuses the same LLM-gateway and tool-calling infrastructure from §8: a migration-specific tool (`migration.suggest_account_mapping(source_account) -> [candidates]`) proposes likely matches between a legacy chart-of-accounts entry (or customer/vendor record) and the new schema, combining structural similarity (Turkish Tekdüzen Hesap Planı account-code patterns most legacy systems share) with semantic similarity (name/description matching).
- Every suggestion carries a confidence score; low-confidence suggestions are flagged for mandatory human review rather than silently applied — the same "AI proposes, human confirms for consequential actions" principle as §8.4, applied to migration instead of day-to-day operations.
- The same matching capability supports deduplication (e.g., one vendor entered three slightly different ways in the legacy system), surfaced as a merge suggestion — never auto-merged without confirmation.

### 9.6 Reconciliation tooling

`reconciliation.py` generates a side-by-side comparison (trial balance, AR/AP aging, stock-on-hand) between values captured at migration time and the legacy system's own reports for the same period. This is as much a trust-building onboarding/sales tool as an engineering QA step, and should be exposed directly in the customer-facing migration progress dashboard (`REQ-DATA-012`), not buried in an internal report.

### 9.7 Security & data handling

- Migration Agent bundles and raw DB backups are encrypted in transit and at rest, and treated as **more sensitive than the platform's own baseline data** — they may contain a full copy of another vendor's database, including data well beyond what the ERP itself needs (`REQ-DATA-014`).
- Raw legacy exports are deleted (not just archived) once a migration is confirmed complete and past its rollback window — data minimization, not indefinite "just in case" retention.
- The Migration Agent executable runs on the customer's own network, outside our infrastructure — it must be minimal, strictly read-only against the source database, digitally signed, and open to inspection by a customer's IT team on request, given the legitimate trust concern of running a third-party tool against production financial data.

### 9.8 Source-system-specific notes — **[DECISION NEEDED]**

- Logo (Tiger/GO/j-Platform) and most Netsis installs run on Microsoft SQL Server; some older Netsis installs use Firebird. Mikro also predominantly runs on SQL Server. None of these vendors publish an official, versioned schema reference — a reliable adapter requires validation against real customer databases, not documentation alone.
- This is exactly why `development-plan.md` Phase 0 recruits design partners before Phase 1 implementation begins, and why Phase 1's exit criteria (`development-plan.md` §4) require a real, not synthetic, customer database to have been migrated successfully through the Logo connector.
- **Open decision**: build this schema knowledge in-house (reverse-engineering against design-partner databases) versus engaging a consultant/freelance integrator already familiar with Logo/Netsis/Mikro's internal structures — a role that exists in the Turkish ERP consulting market — to accelerate the first working connector version. Structurally the same build-vs-partner tradeoff as the GİB connectivity decision (§7.1), and worth resolving alongside it in Phase 0.

---

## 10. Frontend Architecture (Vue)

### 10.1 App shell & package-module loading
- A single Vue SPA with a persistent app shell (nav, header, the AI side-panel) and **lazy-loaded route modules per package**, dynamically registered based on the tenant's `active_packages` (from `Tenant.active_packages`, fetched at login).
- A tenant without the Manufacturing package never downloads the Manufacturing Vue bundle — enforced via Vite's code-splitting + dynamic `import()` gated on the active-packages list, mirroring the backend's "never even runs that code" guarantee (§4).

### 10.2 AI side-panel
- A global, always-mounted component (not per-page), backed by a dedicated Pinia store holding conversation state, connected via the Channels WebSocket/SSE endpoint (§6) for streamed responses.
- Renders citations/drill-down links back to source records (`REQ-CORE-AI-003`) as first-class UI elements, not just plain text — clicking a citation navigates to the actual record.
- Renders a distinct visual treatment for "AI is proposing an action, needs your confirmation" vs. "AI already did this" states, per `REQ-AI-XCUT-003`.

### 10.3 State management
- One Pinia store per package module (`usePurchasingStore`, `useInventoryStore`, ...) plus shared stores (`useAuthStore`, `useAIStore`, `useTenantStore`).
- API calls go through a shared typed API client (generated from the DRF OpenAPI schema — keeps frontend types in sync with backend serializers automatically rather than hand-maintained).

### 10.4 i18n
- `vue-i18n` with Turkish as the default locale and English as the fully-supported alternate (`REQ-NFR-I18N-001/002`) — both ship at Phase 1 launch, not sequentially.
- Locale-aware number/date/currency formatting via `Intl` APIs, not hand-rolled formatting.

### 10.5 Design system
- An internal component library (buttons, tables, forms, approval-workflow widgets) built once in Phase 0/1 on top of Tailwind + headless primitives, so Phases 2–4's ten-plus package modules assemble from existing components rather than each reinventing table/form patterns — directly reduces the risk flagged in `development-plan.md` §9.

### 10.6 POS offline resilience
- The POS module (`REQ-POS-008`) is the one part of the frontend built as a PWA with a service worker and local IndexedDB queue: transactions are queued locally during connectivity loss and synced (with conflict resolution) once the connection returns. This is intentionally scoped to POS only, not the whole app — the general ERP UI does not need offline support, and building it everywhere would be wasted effort against `requirements.md`'s actual scope.

---

## 11. Security Architecture

- **AuthN**: session or short-lived JWT + refresh token for the SPA; SAML/OIDC SSO for Enterprise tier (`REQ-CORE-USR-005`).
- **AuthZ**: RBAC (`REQ-CORE-USR-002`) enforced via DRF permission classes reused identically by the AI tool layer (§8.4/8.5); field-level restrictions (`REQ-CORE-USR-003`) enforced at the serializer level so no code path can accidentally bypass them.
- **Encryption**: TLS 1.2+ in transit (`REQ-NFR-SEC-001`); at-rest encryption via managed Postgres disk encryption plus application-level encryption for the most sensitive fields (payroll bank details, tax IDs) (`REQ-NFR-SEC-002`).
- **Tenant isolation**: schema-per-tenant (§3) as the primary defense; DB connection role per request scoped to the tenant's schema search path, so a query bug can't accidentally cross schemas.
- **KVKK/GDPR**: schema-per-tenant makes "delete all of this data subject's data" (`REQ-NFR-SEC-004`) tractable — for a full-tenant deletion it's a schema drop; for a single data-subject-within-a-tenant request, a documented per-model deletion/anonymization routine is still needed and should be scoped in Phase 1.
- **Data residency [DECISION NEEDED]**: confirm whether Turkish statutory bookkeeping data has a hard in-country hosting requirement or whether documented cross-border safeguards suffice — this determines the cloud region choice in §12 and should be confirmed with a Turkish legal/compliance advisor before Phase 1 infrastructure is finalized.
- **AI-specific security**: prompt-injection awareness for any AI feature that ingests external content (e.g., "draft a PO from this forwarded email" per `REQ-PUR-007`) — treat ingested document/email content as untrusted input, and ensure it cannot itself trigger tool calls without the normal confirmation flow (§8.4).
- **Migration data security**: legacy export bundles and raw DB backups (§9.7) carry the same encryption/retention discipline as any other sensitive data, with the added constraint that they're deleted (not archived) once past the migration rollback window (`REQ-DATA-014`).
- **Secrets management**: environment-based secrets for Phase 0/1; move to a dedicated secrets manager (cloud KMS or Vault) by Phase 2 as team size and environment count grow.
- **Pentest cadence**: per `REQ-NFR-SEC-003` / `development-plan.md` §9, first pass before Phase 1 general availability, then at least annually.

---

## 12. Infrastructure & Deployment

- **Environments**: local (Docker Compose) → staging → production, with schema-per-tenant applying identically in all three (staging uses synthetic tenants, never copies real customer schemas without anonymization).
- **Containerization**: Docker for all services from day one; Kubernetes introduced starting Phase 2 once there's enough tenant/service count to justify the operational overhead — Phase 0/1 can run on a simpler managed container platform.
- **Data residency**: pending the §11 decision, default assumption is a Turkey-region (or nearest-compliant-region) cloud deployment given the concentration of financial/compliance data — confirm before Phase 1 infra lock-in.
- **CI/CD**: GitHub Actions running lint + unit + integration tests on every PR; separate pipeline stage runs the AI golden-query regression suite and the compliance-document schema validation suite before any release touching those areas (`development-plan.md` §9).
- **Migrations**: Django migrations run per-schema for tenant schemas (a `django-tenants` built-in capability) plus once for the shared/public schema — this needs a documented, tested rollback procedure given the schema-per-tenant model's migration fan-out.
- **Observability**: Sentry for exceptions, Prometheus/Grafana for system metrics, plus AI-specific dashboards (per-tenant AI Action credit usage, average query latency, action-approval/rejection rates) feeding both engineering monitoring and the customer-facing "AI Agents Pack" activity dashboard (`REQ-AIAGENT-003`). Migration jobs get their own operational dashboard (bundles received, jobs in dry-run vs. committed, reconciliation pass/fail rates) — a stalled or failing migration is a customer-facing onboarding emergency, not a background job to monitor passively.

---

## 13. Performance & Scalability Considerations

- Indexing strategy prioritizes the highest-cardinality, most-filtered tables first: `JournalLine`, `StockMove`, `AuditLogEntry`, `AIActionLog` — these grow fastest and are queried most.
- Read replicas for reporting/BI queries (`REQ-BI-*`) once a tenant's transaction volume makes reporting queries contend with transactional writes — not needed at Phase 1 scale, planned for Phase 2/3.
- Celery for anything not required synchronously for the user to proceed: report generation, compliance filing submission, AI agent execution, email/SMS sending, migration import processing.
- Stateless Django/Vue serving tiers scale horizontally behind a load balancer; Postgres is the one component requiring deliberate scaling planning (schema-per-tenant connection pooling via PgBouncer becomes relevant well before Phase 3, given `development-plan.md`'s Phase 1 exit criteria already targeting multiple real tenants).

---

## 14. Testing Strategy

| Layer | Tooling | Notes |
|---|---|---|
| Backend unit/integration | `pytest-django` | Every package app tests its models, service layer, and API views |
| Frontend unit/component | Vitest + Vue Test Utils | |
| End-to-end | Playwright | Covers cross-module workflows (e.g., PO → receipt → AP bill → payment) |
| AI evaluation | Custom golden-query regression harness (§8.9) | Runs against the semantic layer + tool registry on every release touching `ai_core` or any package's `ai_tools.py` |
| Compliance validation | Schema validators against the current GİB XSD/format spec | Runs in CI whenever `compliance/turkey/*` changes; also runs against GİB's test environment before each release per `development-plan.md` Phase 1 milestone 2 |
| Migration validation | Fixture-based regression tests against sample Logo/Mikro export bundles, plus the dry-run/reconciliation report checked against expected output | Runs in CI whenever `migration/*` changes; real design-partner databases used for pre-release validation, not just synthetic fixtures (per `development-plan.md` §11 risk on messy real-world data) |
| Security | Automated dependency/vulnerability scanning in CI + periodic manual pentest (`REQ-NFR-SEC-003`) | |
| Load/performance | Locust or k6 against staging before major releases | Validates `REQ-NFR-PERF-*` and `REQ-NFR-SCALE-*` targets |

---

## 15. Third-Party Vendor Decisions Needed

| Decision | Options | Owner / timing |
|---|---|---|
| GİB connectivity path | Direct özel entegratör certification vs. partner API (§7.1) | Phase 0, blocks Phase 1 timeline |
| LLM provider(s) | Primary + fallback model vendor, data-processing terms review | Phase 0, blocks AI architecture spike |
| Cloud provider & region | Must satisfy data-residency decision (§11) | Phase 0 |
| Turkish payment gateway | e.g., iyzico, Param, or equivalent | Phase 2 (when Sales/E-commerce lands) |
| SMS/email provider | Local Turkish SMS gateway + transactional email provider | Phase 1 |
| Object storage provider | S3-compatible, must meet data-residency decision | Phase 0 |
| Legacy schema expertise (Logo/Netsis/Mikro) | Build in-house via design-partner databases vs. engage a specialist integrator/consultant (§9.8) | Phase 0, blocks Phase 1 migration connector timeline |

---

## 16. Open Technical Decisions Summary

1. **Multi-tenancy**: schema-per-tenant recommended (§3) — confirm.
2. **GİB integration path**: partner-first recommended (§7.1) — confirm and select partner.
3. **LLM vendor(s)**: not yet selected (§8.8).
4. **Data residency / cloud region**: pending legal confirmation (§11/§12).
5. **Vector store**: `pgvector` recommended through Phase 3, revisit only if scale demands a dedicated vector DB (§2).
6. **Kubernetes timing**: deferred to Phase 2 — confirm this isn't premature given team's DevOps capacity, or too late given growth expectations.
7. **Migration connector build vs. partner** (§9.8): resolve alongside the GİB decision in Phase 0 — both are "legacy schema/integration expertise" problems with the same build-vs-partner shape.

---

## 17. Repository Structure (Proposed)

```
/backend
  /apps/...            (see §4)
  /config/             (Django settings per environment)
  /manage.py
/frontend
  /src
    /modules/<package>/  (mirrors backend apps 1:1)
    /shared/             (design system, api-client, i18n)
    /ai-panel/
  /vite.config.ts
/infra
  /docker/
  /k8s/                 (from Phase 2)
  /terraform/           (or equivalent IaC, once cloud provider is confirmed)
/migration-agent          (standalone, separately-versioned/signed executable — see §9.2)
  /src
  /build/                (PyInstaller packaging, per-OS builds)
/docs
  product.md
  requirements.md
  development-plan.md
  technical.md
```

A single monorepo (backend + frontend + infra) is recommended through at least Phase 2 — splitting repos before there's a team-scaling reason to (e.g., separate deploy cadences becoming a real bottleneck) adds coordination overhead without benefit at this stage. The `migration-agent` is called out as its own top-level directory (still in the same monorepo) rather than folded into `/backend` because it ships as a separately-versioned, digitally-signed executable distributed to customers — a fundamentally different build/release/trust model than the server-side application code, even while staying in the same repo for now.
