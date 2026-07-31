# Development Plan — AI-Native ERP Platform

**Status:** Draft v1 — companion to [`requirements.md`](./requirements.md) and [`product.md`](./product.md)
**Last updated:** 2026-07-31
**Purpose:** This document sequences the requirements in `requirements.md` into buildable phases — what gets built, in what order, why that order, and what "done" looks like for each phase. Durations are planning-level estimates, not commitments — they depend on team size, which is proposed in §10 but not yet fixed. Every module/feature listed references the `REQ-*` IDs it satisfies, so scope changes stay traceable back to `requirements.md`.

---

## 1. Guiding Principles for Sequencing

1. **Compliance before breadth.** A Turkish ERP with five modules and no working e-Fatura is not viable at all; a Turkish ERP with two modules and rock-solid compliance is. Turkey Localization requirements (`REQ-LOC-TR-*`) are pulled forward into Phase 1, ahead of most operational packages.
2. **AI is built into the foundation, not scheduled as a later phase.** The AI chat layer, permission-aware retrieval, semantic layer, and audit trail (`REQ-CORE-AI-*`, `REQ-AI-XCUT-*`) are Phase 1 scope, not a Phase 3 add-on — retrofitting AI onto a finished Core is exactly the mistake this product is positioned against (see `product.md` §1).
3. **Every phase ships a sellable product**, not an internal milestone. Even Phase 1 must be a real, usable ERP for a small Turkish company, not a demo.
4. **Modularity is a Phase 1 architectural decision, not a Phase 3 refactor.** Core vs. Package boundaries are established before the first package is built, even though only 2 packages exist at the end of Phase 1 (see `technical.md` for how this is enforced at the code level).
5. **Package sequencing follows universal need, not build convenience.** Purchasing and Inventory are almost universally needed and reinforce each other (a PO without stock tracking is half a workflow) — they ship together in Phase 1.

---

## 2. Phase Overview

| Phase | Theme | Est. Duration | Ships |
|---|---|---|---|
| **Phase 0** | Foundation & Validation | 4–6 weeks | Architecture locked, no customer-facing product yet |
| **Phase 1** | MVP — Core + Turkey Compliance | 4–5 months | Sellable Starter/Growth product: Core + Purchasing + Inventory + Turkey compliance |
| **Phase 2** | Operational Expansion | 4 months | + Manufacturing, HR/Payroll, CRM/Sales; Professional tier |
| **Phase 3** | Retail & Broader Reach | 3–4 months | + POS, E-commerce, Advanced BI, AI Agents Pack; first non-Turkey market prep |
| **Phase 4** | Enterprise & Scale | Ongoing | Enterprise tier, dedicated infra, additional localization packs |

Cross-phase workstreams (compliance maintenance, security, AI evaluation, QA automation — §9) run continuously starting in Phase 1 and are **not** "finished" at any phase boundary.

---

## 3. Phase 0 — Foundation & Validation

**Goal:** de-risk the two biggest open decisions from `product.md` before writing product code, and stand up the technical foundation so Phase 1 isn't rebuilding its own plumbing halfway through.

### Decisions to lock
- **Build-vs-partner for GİB connectivity**: become a certified özel entegratör directly, or integrate through an existing one (e.g., a white-label/API partnership) — see `technical.md` §9 for the technical tradeoffs. This decision gates the Phase 1 timeline more than anything else, since özel entegratör certification itself can take months.
- **Multi-tenancy architecture**: schema-per-tenant vs. shared-schema — see `technical.md` §4.
- **Rip-and-replace vs. copilot-on-incumbent wedge** (`product.md` §9 Phase 0): confirmed as **rip-and-replace, full ERP**, given the Django/Vue build decision already made — this plan proceeds on that basis unless revisited.

### Work
- Repo/monorepo setup, CI/CD skeleton, dev/staging environments (`technical.md` §12).
- Core data model design spike covering Tenant, User/Role/Permission, COA/GL, and the AI audit-log schema — these are the hardest things to change later, so they get a dedicated design pass before any package work starts.
- AI architecture spike: prove out the semantic-layer + tool-calling pattern end-to-end on one thin vertical slice (e.g., "what's my current cash position") before committing to it across every module.
- Turkish COA (Tekdüzen Hesap Planı) template sourcing and validation with a real accountant/consultant.
- Recruit 2–3 design-partner companies (small Turkish SMEs willing to pilot Phase 1) — their real data/workflows should shape Phase 1 detail decisions, not just internal assumptions.

### Exit criteria
- Architecture decisions above are documented and signed off.
- A working (non-production) proof-of-concept demonstrates: user login → post a journal entry → ask the AI "what's my cash position" → get a correct, cited answer.
- At least 1 design partner has reviewed and confirmed the proposed Phase 1 scope matches a real need.

---

## 4. Phase 1 — MVP: Core + Turkey Compliance

**Goal:** a real, sellable ERP for a small Turkish company (Starter/Growth tier), with nothing faked or stubbed in the compliance path — this is the phase where the product either proves the core thesis or doesn't.

### Modules & requirements in scope

| Module | Key requirements |
|---|---|
| **Core: Identity/Users/Permissions** | `REQ-CORE-USR-001` to `008` |
| **Core: General Ledger & COA** | `REQ-CORE-GL-001` to `008` |
| **Core: AR/AP** | `REQ-CORE-AR-001/002/003`, `REQ-CORE-AP-001/002`, `REQ-CORE-AR-AP-001` |
| **Core: AI Chat Layer (v1)** | `REQ-CORE-AI-001` to `011` (agentic/metered depth deferred to Phase 2, but the embedded conversational layer and its permission/audit guarantees are Phase 1, non-negotiable) |
| **Core: Compliance Engine (framework)** | `REQ-CORE-LOC-001/002/003` |
| **Core: Audit Trail** | `REQ-CORE-AUDIT-001` to `004` |
| **Core: Base Reporting** | `REQ-CORE-RPT-001` to `003` |
| **Core: Notifications** | `REQ-CORE-NOTIF-001/002` |
| **Core: Document Management** | `REQ-CORE-DOC-001/002` |
| **Turkey Localization (minimum viable set)** | `REQ-LOC-TR-001` (e-Fatura), `REQ-LOC-TR-002` (e-Arşiv), `REQ-LOC-TR-003` (e-Defter), `REQ-LOC-TR-007` (KDV beyanname), `REQ-LOC-TR-008/009/010` |
| **Purchasing / Procurement** | `REQ-PUR-001` to `007` |
| **Inventory & Warehouse (core, non-manufacturing)** | `REQ-INV-001` to `008` |
| **Data Migration & Onboarding** | `REQ-DATA-001` to `004`, `REQ-DATA-005` (Logo connector — first version: COA, master data, open AR/AP balances), `REQ-DATA-007` to `010`, `REQ-DATA-012` to `016` |
| **NFRs baseline** | `REQ-NFR-PERF-*`, `REQ-NFR-SEC-001/002/003/004/006/007`, `REQ-NFR-I18N-*`, `REQ-NFR-AVAIL-001/002` |

Explicitly **not** in Phase 1: e-İrsaliye and e-Müstahsil (`REQ-LOC-TR-004/005` — pulled into Phase 2 since they only bind at higher revenue/role thresholds), Manufacturing, HR/Payroll, CRM, POS, e-commerce, Advanced BI, AI Agents Pack, multi-entity consolidation, SSO/Enterprise features. The Mikro connector (`REQ-DATA-006`) and full historical-transaction depth (`REQ-DATA-011`, beyond opening balances) are deferred to Phase 2 — see below.

### Why Purchasing + Inventory first (not CRM or HR)
Every company doing any physical goods handling needs both, they reinforce each other end-to-end (PO → receipt → stock → AP bill), and neither carries the regulatory complexity that HR/Payroll (SGK) does — keeping Phase 1's non-compliance surface area small so the team's attention stays on getting compliance right.

### Why a direct Logo connector ships in Phase 1, not later
Migration tooling is only a real differentiator (per `product.md` §2 pillar 6 and §8 GTM point 6) if it works against the legacy system prospects actually run — and per the Turkey market research in `product.md` §3.3, that's overwhelmingly Logo (Tiger/GO/Netsis family). A generic spreadsheet importer alone doesn't remove the switching-cost objection in a live sales conversation; a working Logo connector does. Mikro is deferred to Phase 2 deliberately (smaller relative share of the earliest target segment, and the team shouldn't build two unproven legacy-schema connectors before validating the pattern once against real design-partner data — see `technical.md` §9.10 on why this requires access to real customer databases, not just documentation).

### Milestones
1. Core ledger + AR/AP functional, validated against a real accountant's expectations of a Turkish trial balance.
2. e-Fatura/e-Arşiv generation validated against GİB's test (test ortamı) environment, not just internally — this is a hard gate, not a nice-to-have check.
3. AI chat answering real questions across GL/AR/AP/Purchasing/Inventory data with correct, cited answers on a golden-query eval set (see §9).
4. Design partners are running real transactions through the system in parallel with their existing tool (Logo/Excel/etc.) without a critical data or compliance discrepancy.
5. At least one design partner's real Logo database has been migrated end-to-end through the connector (not a manual/spreadsheet workaround) and reconciled against their legacy trial balance.

### Exit criteria
- All Phase 1 `REQ-*` items implemented and tested per `requirements.md` §12 Definition of Done.
- At least one design partner has fully cut over their real e-Fatura/e-Defter filing through the new system for a live filing period.
- The Logo migration connector has successfully imported at least one real (not synthetic) customer database, with a reconciliation report confirming trial balance and AR/AP aging match within an agreed tolerance.
- No open Sev-1/Sev-2 security findings from an initial security review (`REQ-NFR-SEC-003`).

---

## 5. Phase 2 — Operational Expansion

**Goal:** cover the operational needs of a growing SME (Growth → Professional tier) and complete the Turkey compliance surface for larger/employing businesses.

### Modules & requirements in scope

| Module | Key requirements |
|---|---|
| **Manufacturing / Production (MRP)** | `REQ-MFG-001` to `007` |
| **HR & Payroll (Turkey-aware)** | `REQ-HR-001` to `007` |
| **Sales & CRM** | `REQ-CRM-001` to `006` |
| **Turkey Localization (completion)** | `REQ-LOC-TR-004` (e-İrsaliye), `REQ-LOC-TR-005` (e-Müstahsil), `REQ-LOC-TR-006` (SGK e-Bildirge, tied to HR/Payroll landing this phase) |
| **Core: Multi-entity** | `REQ-CORE-ENT-001/002` |
| **AI: metered agentic layer** | Introduce "AI Action credits" billing/metering infra underlying `REQ-CORE-AI-011`; first agentic workflows (e.g., reconciliation sweep) as a preview of the Phase 3 Agents Pack |
| **Data Migration (connector expansion)** | `REQ-DATA-006` (Mikro connector), `REQ-DATA-011` (deepen historical transaction import beyond opening balances, extended to both Logo and Mikro connectors) |
| **NFR maturity** | `REQ-NFR-SCALE-*`, `REQ-NFR-SEC-005` (GDPR groundwork ahead of Phase 3 international prep), `REQ-NFR-AVAIL-003` |

### Dependencies
- HR/Payroll's SGK e-Bildirge requirement (`REQ-LOC-TR-006`) is why HR/Payroll and the e-İrsaliye/e-Müstahsil completion land in the same phase — both are compliance-driven, and the compliance team's context-switching cost is lower doing them together.
- Multi-entity (`REQ-CORE-ENT-*`) is scoped here because it's a prerequisite for Professional-tier pricing (`product.md` §7.2), not because any package technically requires it.
- The Mikro connector builds on the migration pipeline (mapping UI, dry-run/reconciliation tooling) proven out in Phase 1 against Logo — it's a second adapter on an already-validated architecture, not a new build.

### Exit criteria
- Professional tier is sellable: multi-entity consolidation works end-to-end for at least one real multi-entity design partner.
- SGK e-Bildirge submission validated against SGK's own test process.
- Metered AI billing is live and reconciles correctly against actual usage for at least one full billing cycle.
- The Mikro migration connector has successfully imported at least one real customer database with a passing reconciliation report.

---

## 6. Phase 3 — Retail & Broader Reach

**Goal:** cover retail-specific workflows, open the e-commerce channel, and ship the fuller AI-native promise (Advanced BI + Agents Pack) — plus lay groundwork for the first non-Turkey market.

### Modules & requirements in scope

| Module | Key requirements |
|---|---|
| **POS / Retail** | `REQ-POS-001` to `008` (including fiscal device integration and offline resilience) |
| **E-commerce Integration** | `REQ-ECOM-001` to `003` |
| **Advanced BI / Analytics** | `REQ-BI-001` to `004` |
| **Advanced AI Agents Pack** | `REQ-AIAGENT-001` to `003` |
| **International readiness** | Generalize the Localization Engine (`REQ-CORE-LOC-001`) beyond a Turkey-only implementation in practice, not just in theory; full `REQ-NFR-SEC-005` GDPR compliance |

### Notes
- POS's offline-resilience requirement (`REQ-POS-008`) and fiscal device integration (`REQ-POS-003`) are the highest-risk items in this phase from a technical standpoint — flagged for early spike work at the start of the phase, not left until the end.
- The Advanced AI Agents Pack depends on the metered AI infrastructure built in Phase 2 — sequencing this after Phase 2, not in parallel, is deliberate.

### Exit criteria
- POS running live in at least one retail design partner, tested through a full day's Z-report cycle.
- E-commerce sync validated with at least one real marketplace integration (order + stock + invoice generation).
- First AI Agents Pack customer running at least one autonomous scheduled agent in production with a measurable time-saved metric.

---

## 7. Phase 4 — Enterprise & Scale

**Goal:** support larger, more complex customers and expand the compliance-engine pattern to additional geographies.

### Scope
- Enterprise tier: SSO/SAML (`REQ-CORE-USR-005`), dedicated/VPC infrastructure option (`REQ-NFR-SEC-010`), custom agent development tooling (per `product.md` §6.2 Advanced AI Agents Pack "Enterprise-only" capabilities).
- Deepened multi-entity consolidation for complex group structures.
- First additional country Localization Pack, built using the now-proven pluggable pattern from Turkey (`REQ-CORE-LOC-001`).
- Public API maturity for Enterprise customer-built integrations (`REQ-INT-007`).

This phase is intentionally less detailed than Phases 1–3 — it should be re-scoped based on what's actually learned from real customers in the earlier phases rather than planned in detail now.

---

## 8. Phase-to-Requirement Traceability Summary

| Requirements area | Phase |
|---|---|
| Core Identity/Users/Permissions | 1 |
| Core GL/AR/AP | 1 |
| Core AI Chat (base) | 1 |
| Core Compliance Engine (framework) | 1 |
| Core Audit Trail | 1 |
| Turkey e-Fatura/e-Arşiv/e-Defter/KDV | 1 |
| Purchasing | 1 |
| Inventory | 1 |
| Data Migration | 1 |
| Manufacturing | 2 |
| HR & Payroll | 2 |
| Sales & CRM | 2 |
| Turkey e-İrsaliye/e-Müstahsil/SGK | 2 |
| Multi-entity | 2 |
| Metered AI / Agentic preview | 2 |
| POS | 3 |
| E-commerce | 3 |
| Advanced BI | 3 |
| Advanced AI Agents Pack | 3 |
| Enterprise tier / SSO / dedicated infra | 4 |
| Additional country localization | 4 |

---

## 9. Cross-Phase Workstreams (Continuous, Not Phase-Bound)

- **Compliance maintenance.** A permanent function (not a project), tracking GİB Tebliğ changes starting in Phase 1 and never "finished" (`REQ-LOC-TR-009`). This team/role should exist before Phase 1 ships, not be hired reactively after the first threshold change breaks something.
- **AI evaluation & golden-query library.** Starts in Phase 0's proof-of-concept and grows continuously — every phase adds new golden queries covering its new modules, and regressions are tested automatically before each release (ties to `requirements.md` §12 Definition of Done, item 3).
- **Security & penetration testing.** Per `REQ-NFR-SEC-003`, at least annually and before each major release — first pass should happen before Phase 1 general availability, not after.
- **QA/test automation.** Grows alongside each phase's modules; compliance-relevant output (e-Fatura XML, e-Defter berat) gets its own automated validation suite against the GİB schema, separate from ordinary feature tests.
- **Design system / UI component library.** Established in Phase 0/1 so Phases 2–4 are assembling from existing components, not re-inventing UI patterns per package.
- **Migration & connector library.** Starts in Phase 1 with the Logo connector and never really "finishes" — like compliance, this grows over time (Mikro in Phase 2, additional/updated connectors as new legacy versions or customizations are encountered) and needs a permanent owner who tracks connector accuracy against real customer data, not just a one-time project team. Every new design partner with an unfamiliar data shape is a potential connector regression, not just a one-off onboarding task.

---

## 10. Team & Resourcing (Proposed)

This is a starting proposal for discussion, not a final headcount plan — right-size against actual budget/hiring constraints.

| Phase | Suggested composition |
|---|---|
| Phase 0 | 1 tech lead/architect, 1–2 senior backend (Django) engineers, 1 senior frontend (Vue) engineer, 1 AI/ML engineer, part-time Turkish tax/compliance consultant |
| Phase 1 | + 1–2 additional backend engineers, 1 additional frontend engineer, 1 dedicated compliance specialist (full-time from here on), 1 migration/integration engineer (owns the Logo connector and the generic import pipeline), 1 QA engineer, 1 product/design |
| Phase 2 | + 1 backend engineer (Manufacturing/HR domain complexity), 1 payroll/SGK compliance specialist, DevOps/SRE role becomes dedicated (not shared) — the Phase 1 migration engineer extends coverage to the Mikro connector rather than a new hire, since the pipeline is already built |
| Phase 3 | + 1 frontend engineer (POS offline/fiscal-device complexity), 1 integrations engineer (e-commerce marketplace APIs) |
| Phase 4 | + Enterprise-focused solutions engineer, security engineer (dedicated), second-country compliance specialist as that market is entered |

---

## 11. Risks Tied to Phasing

| Risk | Phase most exposed | Mitigation |
|---|---|---|
| Özel entegratör certification/partnership takes longer than expected, delaying compliance-dependent Phase 1 exit | Phase 0/1 | Resolve the build-vs-partner decision in Phase 0 with enough lead time buffer; prefer a partner path if certification timeline is uncertain |
| GİB changes a threshold/format mid-build | All, especially 1–2 | Compliance workstream (§9) is continuous and monitors GİB Tebliğ on an ongoing basis, not just at each module's build time |
| AI accuracy issues surface only after Phase 1 ships broadly | 1 onward | Golden-query eval gate is part of Definition of Done from Phase 0's proof-of-concept forward, not introduced later |
| Design partners' real workflows reveal Phase 1 scope gaps late | 1 | Design partners recruited in Phase 0, reviewing scope before, not after, implementation begins |
| POS offline/fiscal-device integration proves harder than estimated | 3 | Flagged for early spike at the start of Phase 3, not left to the end of the phase |
| Logo/Mikro legacy schemas are undocumented, version-fragmented, and full of years of manual workarounds — the connector could underperform against real (messy) customer data even after working in early tests | 1–2 | Build and validate the connector against real design-partner databases (not synthetic test data) before calling it done; keep the generic import fallback (`REQ-DATA-007`) as a safety net for anything the connector can't confidently handle, rather than blocking a migration entirely |

---

## 12. What "Done" Means Per Phase (Summary)

Each phase is done when: (a) every in-scope `REQ-*` item meets the Definition of Done in `requirements.md` §12, (b) at least one real design-partner/customer is using the phase's new capability in production, not just staging, and (c) the cross-phase workstreams (§9) have no open Sev-1/Sev-2 issues attributable to that phase's new scope.
