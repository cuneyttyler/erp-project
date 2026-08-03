# Open Decisions & Blockers

**Status:** living document — tracks decisions that are blocking further Phase 1 progress and need input from Cüneyt specifically (commercial/legal/business calls, not engineering ones). See `development-plan.md` §4 for how these fit into Phase 1 exit criteria.

**Last reviewed: 2026-08-02 — both decisions below are still open, no answer given yet.** Development continues into unblocked Phase 2 scope in the meantime (see `feedback.md`-driven UI work).

---

## 1. GİB connectivity: build vs. partner (blocks Turkey compliance)

**What's blocked:** e-Fatura, e-Arşiv, e-Defter, and KDV beyanname generation — the "Turkey Localization (minimum viable set)" item in `development-plan.md` Phase 1, and a hard Phase 1 exit gate ("e-Fatura/e-Arşiv generation validated against GİB's test environment"). Also now blocks two Phase 3 items on the same basis: POS fiscal payment device integration and POS-originated e-Arşiv receipt generation (`REQ-POS-003/007`, `REQ-LOC-TR-011` — see §7 below).

**The decision** (fully laid out in `technical.md` §7.1):

| Option | What it means | Tradeoff |
|---|---|---|
| **A. Become a certified özel entegratör** | Direct GİB integration, our own signing infrastructure (mali mühür), full control over the filing pipeline | Real certification cost/time/security-audit overhead before Phase 1 can even exit — directly threatens the Phase 1 timeline |
| **B. Integrate through an existing özel entegratör** | Call a partner's API (e.g. Foriba/Sovos, İzibiz, Uyumsoft, Nesbilgi) for e-Fatura/e-Arşiv/e-Defter generation and GİB transmission; our `compliance/turkey/` adapter becomes a thin wrapper over their API | Faster to a working Phase 1; recurring per-document/per-tenant cost from the partner; some loss of control over the exact filing pipeline |

**Recommendation on file:** Option B for Phase 1 — revisit direct certification only once tenant volume justifies the fixed cost. The internal interface (`generate_e_invoice(invoice) -> FilingResult`) is designed so swapping the underlying implementation later is a refactor, not a rewrite.

**What's needed from you:** confirm Option B, and if so, which specific partner to evaluate/contract with. This is a commercial negotiation (pricing, SLAs, data-processing terms), not something I can resolve by writing more code.

---

## 2. Legacy-schema access: build vs. partner (blocks the Logo migration connector)

**What's blocked:** the Logo migration connector (`REQ-DATA-005`) — part of the same Phase 1 exit criteria ("the Logo migration connector has successfully imported at least one real customer database").

**The decision** (`technical.md` §9.8):

Logo (Tiger/GO/j-Platform) and most Netsis installs run on Microsoft SQL Server; some older Netsis installs use Firebird. None of these vendors publish an official, versioned schema reference — a reliable connector requires validation against **real customer databases**, not documentation alone.

| Option | What it means |
|---|---|
| **Build in-house** | Reverse-engineer the schema ourselves against design-partner databases as they're recruited (`development-plan.md` Phase 0) |
| **Engage a specialist integrator/consultant** | Someone already familiar with Logo/Netsis/Mikro's internal database structures — a role that exists in the Turkish ERP consulting market — to accelerate the first working connector version |

**What's needed from you:** same shape as decision #1 — pick a path, and if it's the consultant route, a name/contact to start with. Also worth deciding alongside this: **do we have (or can we get) access to a real Logo/Netsis database to build against?** Without one, the connector can only be built against guesses, which is exactly the trap `product.md`'s risk register warns about (legacy data being "a bottomless services pit instead of a repeatable product feature").

---

## 3. Related, lower-priority: data residency / cloud region

Flagged in `technical.md` §10/§11/§15 — confirm whether Turkish statutory bookkeeping data has a hard in-country hosting requirement or whether documented cross-border safeguards suffice. Not blocking Phase 1 engineering work today (we're on your local Postgres for now), but it does determine the cloud provider/region choice before any real production deployment, so it's worth resolving before that becomes urgent rather than after.

---

## 4. AI Chat Layer v1: needs an LLM API key to actually talk (not a blocker on building it)

**What's built:** the read-only Q&A path (`REQ-CORE-AI-001/002/003/004/005/006/008/009`) — `apps/ai_core` (semantic-layer registry + tool-calling loop over Claude + audit logging) plus a `metrics.py`-equivalent (`ai_tools.py`) in every package (Core, Inventory, Purchasing, Sales & CRM, Manufacturing, HR & Payroll) registering read-only questions the assistant can answer with a real, cited figure — cash position, AR/AP aging, stock on hand, open POs/SOs/leads, pending work orders, latest payroll cost. The frontend AI side-panel (already scaffolded from Phase 0) is now wired to it end-to-end.

**Status: live.** `ANTHROPIC_API_KEY` is set in `backend/.env` (2026-08-02) and the full pipeline has been smoke-tested end-to-end against the real Anthropic API, not just the mocked test suite: asked "Nakit durumum nedir?" in Turkish, the assistant correctly called the `cash_position` tool, got the real figure (10.000,00 TL), and narrated a correct, cited, fluent Turkish answer. `AI_LLM_MODEL` (defaults to `claude-sonnet-5`) is configurable in `.env` if a different model/tier is wanted later.

**The write/action path is now built too** (`REQ-CORE-AI-007/010`, §8.4, Phase 2 scope in `development-plan.md` §5's "metered agentic layer"): a parallel `apps.ai_core.actions` registry (mirrors `semantic.py` exactly, but for mutations) plus a durable `PendingApproval` state machine (`pending → executed|failed`, or `pending → rejected` — one-way, same discipline as `JournalEntry.post()`). Calling a registered action from the chat loop never executes it — it creates a `PendingApproval` row with a read-only preview and surfaces it to the frontend as `pending_action`; the actual mutation only happens via the new `PendingApprovalViewSet.approve` endpoint, using the *approving* user's own session, never an elevated AI account. Two actions are wired end-to-end as the reference pattern: `create_journal_entry` (Core, thin wrapper over `JournalEntrySerializer`) and `approve_leave_request` (HR & Payroll, calls the same `LeaveRequest.approve()` the REST endpoint's own approve action uses). The AIPanel now renders live Approve/Reject buttons on a pending card and reflects `executed`/`failed`/`rejected` back once resolved. Live-verified end-to-end via Playwright against the real Anthropic API on 2026-08-02: asked "Please approve leave request #35," the assistant correctly proposed (not executed) the action, the panel showed the confirmation card, clicking Approve resolved it and the leave request's status flipped to `approved` with a matching audit-log entry.
- **Per-tenant configurable auto-approve threshold** (`REQ-CORE-AI-010`'s "configurable" half): NOT implemented — every write action unconditionally requires confirmation regardless of size/type, the same "one fixed gate, not a configurable multi-level threshold" scope cut already made for `PurchaseOrder.APPROVAL_THRESHOLD`. Real follow-up work if a design partner asks for it.
- **Metered AI Action credits / billing** (`REQ-CORE-AI-011`, §8.8): the *ledger* is real now — `AIUsageRecord` writes one row (model, input/output tokens) per LLM call via `apps.ai_core.metering.record_usage()`, called from `chat.answer()` after every `llm_gateway.create_message()`. What's NOT built: translating that ledger into an actual metered charge, enforcing a spend cap, or invoicing — the billing/credit-balance reconciliation on top of the ledger is real follow-up work, not hidden behind the model existing.
- **First agentic workflow preview** (development-plan.md §5's "first agentic workflows... as a preview of the Phase 3 Agents Pack"): `apps.core.agents.run_ar_reconciliation_sweep()` — flags AR invoices overdue past a threshold across every entity, writes an `AuditLogEntry` (`actor="ai:system"`). Wired to a Celery task (`apps/core/tasks.py`, iterates every tenant schema) and a management command (`run_reconciliation_sweep`) for manual/cron triggering, but **not** wired to an actual Celery beat schedule yet — this is one concrete, hard-coded workflow proving the shape works, not the general `REQ-AIAGENT-001/002/003` framework (scheduled/trigger-based workflow definition UI, activity dashboard), which stays Phase 3 scope.
- **RAG over uploaded documents** (§8.7) — contract/policy Q&A isn't wired; today's assistant only answers questions the registered metrics can compute, or proposes the registered write actions.
- **Golden-query regression eval** (§8.9) — no automated accuracy-regression suite yet; today's test coverage is unit/integration correctness of each metric/action and the tool-calling loop's control flow, not answer-quality evaluation against real English/Turkish phrasing variety.
- **Conversation persistence** — each chat turn is stateless server-side beyond the audit log; the frontend resends prior turns as context. A durable conversation history model is a small addition later if it's wanted (e.g. for a "recent conversations" list), not a redesign.

## 5. Configurable Data Views (from docs/feedback.md "Feedback 1") — mostly rolled out

**What's built:** `REQ-CORE-UX-001..005` — a reusable `DataTable.vue` component (column drag-reorder, show/hide, resize, per-column sort/filter, inline click-to-edit) plus a backend `SavedView` model/API (`Core: /api/v1/core/saved-views/`) for personal-vs-shared named "variants" per screen, exactly matching the feedback's "I want a/b/c wide, someone else wants a/b/d/f narrow" example. The left sidebar is grouped into collapsible sections (Finans / Envanter & Satın Alma / Satış & CRM / Üretim / İK & Bordro) instead of one flat list.

**Rollout status:** 14 of 18 data-table screens are on `DataTable.vue` now — every genuinely flat, one-row-per-record list: Items, Invoices, Chart of Accounts, Journal Entries, Trial Balance, Parties, Bills, Aging, Warehouses, Stock Levels, Leads, Work Orders, Employees, Leave Requests. Verified live via Playwright across all of them (render check + a real inline-edit round-trip against the backend on Chart of Accounts).

**Deliberately left as their original card-based UI, not a DataTable gap:** Purchase Orders, Sales Orders, BOMs, and Payroll Runs. Each of these is a master-detail workflow — a header record with its own nested, independently-actioned line-item table (receive/fulfill quantities per line, payslips per run) — not a flat row list, and forcing DataTable's single-row model onto that would be a worse fit than the current expandable-card UI. If a shared expandable-row pattern is wanted for these later, that's a real (separate) extension to `DataTable.vue`, not a rollout gap to close with the existing component.

**Known limitations, same as before:** column resize is mouse-drag only (no keyboard/touch equivalent); filtering is a case-insensitive text-contains match on rendered cell text, not column-type-aware (no date-range/numeric-range filters) yet.

## 6. Multi-entity consolidation (REQ-CORE-ENT-001/002) — shipped, scoped to GL/AR/AP

**What's built:** a new `Entity` model (Core) — a tenant can now operate multiple legal companies under one subscription, each with its own Chart of Accounts, journal entries, and customer/vendor master data. A header switcher (next to the locale selector) picks which entity is "current"; every GL/AR/AP screen reads and writes through that selection. Trial balance supports both a single-entity view and a **Konsolide** (consolidated) view that sums every entity's posted balances together, with accounts flagged `is_intercompany` excluded from the consolidated total (REQ-CORE-ENT-002's elimination requirement, simplified to "drop the account entirely" rather than transaction-level matching/netting — flagged in `Account.is_intercompany`'s docstring, same discipline as every other simplified financial calculation in this codebase).

**Deliberately scoped narrow:** only Account, JournalEntry, and Party (and Invoice/Bill transitively, via `party.entity`) are entity-scoped. Items, Warehouses, and every operational package (Purchasing/Inventory/Sales/Manufacturing/HR & Payroll) stay tenant-wide — those are genuinely shared master data/physical operations across a corporate group, not something REQ-CORE-ENT-001 ("own COA, ledgers, and statutory filings") actually asked to split. Revisit if a real multi-entity design partner needs operational segregation too.

**What's needed from you, eventually, not urgently:** `product.md` §7.2 gates multi-entity to the Professional tier+, but `active_packages` only models per-package gating today, not subscription tier — so every tenant can use it right now regardless of plan. Building real tier-gating (or deciding it's not worth gating separately from the Professional package bundle) is a small follow-up, not a blocker.

**A real bug this caught, worth remembering:** `Account`/`JournalEntry`/`Party`'s new `entity` field is `null=True` at the DB level (for migration-backfill simplicity) but required via the API. Enforcing that via `Meta.extra_kwargs = {"entity": {"required": True}}` looked right and passed the whole test suite -- but DRF's own ModelSerializer auto-generation adds an implicit `default=None` for any nullable FK *before* extra_kwargs are layered on, and the combination trips DRF's internal "may not set both `required` and `default`" assertion -- a 500 on every single list/create call, only surfaced by a live Playwright run hitting the actual list endpoint, not by any automated test (none of the existing tests happened to exercise a plain `GET` against the affected endpoints in a way that triggered it). Fixed by declaring the field explicitly (`entity = serializers.PrimaryKeyRelatedField(queryset=Entity.objects.all())`) instead of relying on `extra_kwargs`, with a regression test added afterward. Worth remembering next time a required-but-nullable FK gets added to a serializer.

## 7. POS / Retail (development-plan.md §6, Phase 3) — core module shipped, fiscal/e-Arşiv gap flagged

**What's built:** a full `apps.pos` package (REQ-POS-001/002/004/005/006) -- multi-store/multi-till setup (`Store`/`Till`, each store tied to one `Entity` and one Inventory `Warehouse`), shift open/close, checkout (`apps.pos.services.checkout`) that atomically deducts stock via Inventory's own service layer and posts a balanced GL journal entry, returns/exchanges with automatic inventory and GL reversal, and a Z-report (`POSShift.z_report()`) giving the cash/sales reconciliation an till operator needs at close. Frontend: a checkout screen (cart + split payment), a shifts screen (open/close + Z-report), and a store/till setup screen. Live-verified end-to-end via Playwright on 2026-08-02: opened a shift, rang up a sale, closed the shift, confirmed the Z-report's cash reconciliation matched. 33/33 backend tests passing.

**REQ-POS-008 (offline resilience) is real, not a stub:** `src/modules/pos/offlineQueue.ts` queues a checkout in IndexedDB when the network request fails outright, and replays the queue (via the same idempotent `client_reference` the backend already enforces uniqueness on) once connectivity returns or the screen reloads. `public/pos-sw.js` is a minimal network-falling-back-to-cache service worker so the POS screen itself stays loadable through a reload/reopen while offline -- deliberately *not* a full precached PWA (that needs `vite-plugin-pwa` or equivalent build tooling, not pulled in for this pass); its real limits are documented in the file itself (first visit must be online, opportunistic caching only, API responses are never cached/served stale).

**What's blocked, same root cause as SGK e-Bildirge/the Mikro connector (§1/§2 above):** fiscal payment device integration and POS-originated e-Arşiv receipt generation (`REQ-POS-003/007`, `REQ-LOC-TR-011`) need the same GİB-connectivity decision (build vs. partner özel entegratör) that's blocked every other Turkey compliance filing since Phase 1. A `POSSale` is a real, GL-posted transaction today -- what's missing is the statutory fiscal receipt/e-Arşiv document generated *from* it, exactly the same "the adapter interface is designed for later, the actual filing pipeline isn't wired" shape as e-Fatura.

**Deliberate scope cuts, not gaps:** no per-line VAT/tax-rate breakdown (same simplification `InvoiceLine`/`BillLine` already make -- `unit_price` is a flat line amount); REQ-POS-006 ("loyalty/discount program configuration") is a manual discount amount per line at checkout, not a persistent customer-linked points-accrual program.

## 8. E-commerce integration (REQ-ECOM-001/003, development-plan.md §6, Phase 3) — architecture + Shopify adapter shipped, not live-verified

**Decision on file (asked you directly before building, 2026-08-03):** you chose "build now, verify later" over waiting for real marketplace credentials -- Trendyol/Hepsiburada require an approved Turkish merchant account to get API access (not self-serve), and no Shopify developer/sandbox credentials were available either. Same shape as the Logo/Mikro connector decision (§2), scoped down to "build the pattern, flag it as unverified" rather than fully blocking on it.

**What's built:** `apps.ecommerce` -- `MarketplaceAccount` (one connected shop, tied to an `Entity` and an Inventory `Warehouse`, credentials write-only at the API layer), `MarketplaceListing` (maps one of our Items to the marketplace's own SKU/variant/location ids), and `MarketplaceOrder` (a dedup/audit record, unique per account+external order id so re-running a sync is always safe). `adapters.py` defines a country/platform-agnostic `MarketplaceAdapter` interface -- the same "pluggable implementation behind one internal interface" shape as `compliance/turkey/engine.py`'s `file(filing_type, payload) -> FilingResult` (technical.md §7.1) -- with `ShopifyAdapter` as the reference implementation, written against Shopify's public, versioned Admin REST API docs. `services.sync_orders()` pulls new orders in as real, confirmed `SalesOrder`s via a new `apps.sales_crm.services.create_order()` public entry point (added so `apps.ecommerce` never reaches into `sales_crm`'s models directly, per technical.md §4's cross-app rule) -- an order whose SKU has no listing mapping is marked `failed` with a reason, never silently dropped. `services.push_stock_levels()` (REQ-ECOM-003) pushes current on-hand quantity for every mapped listing to prevent overselling. Sync is poll-based (fetch "everything since last sync"), triggered manually from the UI, a management command, or a Celery task (no beat schedule yet, same state as the AR reconciliation sweep) -- not webhook-driven, since a webhook receiver needs a public HTTPS endpoint and real per-platform signature verification against a live store.

**Verification status, stated plainly:** 25/25 backend tests pass, all against a mocked `requests` layer -- the adapter has never been exercised against a real Shopify store. It *has* been proven against Shopify's real infrastructure once, incidentally: a live Playwright run pointed it at a nonexistent `*.myshopify.com` domain and the request correctly reached Shopify's actual servers (a real 404 came back, not a DNS/connection failure), confirming the request shape matches their documented API -- but this is not the same as a successful sync against real data. Treat `ShopifyAdapter` as "real code, first live verification still pending," not a stub.

**What's blocked, same root cause as SGK e-Bildirge/the Mikro connector/POS fiscal (§1/§2/§7):** REQ-ECOM-002 (auto-generate e-Arşiv invoices for e-commerce/B2C orders) needs the same GİB-connectivity decision. A synced marketplace order becomes a real SalesOrder; the statutory e-Arşiv document generated from it is what's missing.

**A real gap, not hidden:** `MarketplaceAccount.api_key`/`api_secret` are stored as plaintext at the DB level -- write-only at the serializer layer (never returned by the API once set) is the only mitigation today. Field-level encryption or a secrets-manager reference is real follow-up work before this should hold a real merchant's live credentials.

## What's proceeding despite the two open decisions above

Per your instruction, Phase 1 continued into **Phase 2 scope** (`development-plan.md` §5), completed it, and — per your go-ahead — is now into **Phase 3 scope** (`development-plan.md` §6) where it doesn't depend on either decision above. Sales & CRM, Manufacturing, HR & Payroll, the AI Chat Layer v1, Configurable Data Views, multi-entity consolidation, the metered AI agentic layer, POS/Retail (§7), and now E-commerce integration (§8) have all shipped. The items still genuinely blocked are the same ones flagged since Phase 1, plus the fiscal/e-Arşiv pieces of POS and e-commerce which turned out to share the identical blocker: SGK e-Bildirge, the Mikro connector, POS fiscal-device/e-Arşiv integration, and e-commerce e-Arşiv generation all need decision #1 and/or #2 above — your input, not more engineering.
