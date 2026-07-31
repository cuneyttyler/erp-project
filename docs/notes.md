# Open Decisions & Blockers

**Status:** living document — tracks decisions that are blocking further Phase 1 progress and need input from Cüneyt specifically (commercial/legal/business calls, not engineering ones). See `development-plan.md` §4 for how these fit into Phase 1 exit criteria.

---

## 1. GİB connectivity: build vs. partner (blocks Turkey compliance)

**What's blocked:** e-Fatura, e-Arşiv, e-Defter, and KDV beyanname generation — the "Turkey Localization (minimum viable set)" item in `development-plan.md` Phase 1, and a hard Phase 1 exit gate ("e-Fatura/e-Arşiv generation validated against GİB's test environment").

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

## What's proceeding despite these blockers

Per your instruction, Phase 1 continues into **Phase 2 scope** (`development-plan.md` §5) where it doesn't depend on either decision above — starting with **Sales & CRM**, which mirrors the Purchasing pattern already shipped (Sales Order → fulfillment → stock pick → auto-generated customer Invoice, the mirror image of PO → receive → stock receipt → auto-generated vendor Bill).
