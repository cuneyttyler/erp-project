# Customer Requirements Document — AI-Native ERP Platform

**Status:** Draft v1 — companion to [`product.md`](./product.md)
**Last updated:** 2026-07-31
**Purpose:** This document specifies *what the product must do*, from the customer's point of view, in enough detail that it can be turned directly into a development plan and technical design. It does not describe how anything is built (see `technical.md`) or when (see `development-plan.md`).

**Requirement ID convention:** `REQ-<AREA>-<NNN>`. IDs are stable once assigned — do not renumber, only append or mark superseded. `development-plan.md` and `technical.md` reference these IDs, so treat them as the traceability backbone of the whole project.

---

## 1. Document Purpose & Scope

This is a customer/business requirements document, not a technical spec. It describes the application a customer signs up for: what modules exist, what each one must do, who uses it, and what it must guarantee (compliance, security, performance). Every functional area is broken into **Core Platform** (mandatory, bundled with every subscription) and **Packages** (independently priced, opt-in), consistent with the packaging model defined in `product.md` §6.

Scope covers the full target product across all phases — this is the complete requirements set, not just an MVP slice. `development-plan.md` decides which requirements land in which phase.

---

## 2. Product Overview

### 2.1 What the product is
A multi-tenant, cloud-based (SaaS) Enterprise Resource Planning system, sold in modular packages built around one shared Core, with an AI assistant embedded across every screen and workflow. Primary market is Turkey (with full local e-government compliance); secondary market is English-speaking SMB/mid-market.

### 2.2 Deployment model
- Multi-tenant SaaS by default (one customer = one tenant, logically isolated data).
- Enterprise tier may require dedicated/isolated infrastructure (see `REQ-NFR-SEC-010`).
- Web application, accessed via modern browsers; no required desktop install. A subset of POS functionality must tolerate intermittent connectivity (see `REQ-POS-008`).

### 2.3 Languages
- Turkish and English are both first-class languages from the first release — not Turkish-only with English bolted on later, and not English-only with Turkish added later. Every user-facing string, error message, report, and AI response must exist in both.

### 2.4 Who is a "customer"
- A company (tenant) that subscribes to the platform, ranging from a 1-person sole proprietorship (Starter) to a multi-entity group (Enterprise). See §3 for the roles within a customer organization.

---

## 3. User Roles & Personas

| Role | Description | Primary needs |
|---|---|---|
| **Owner/Admin** | Business owner or general manager; usually the buyer | Full visibility, billing/subscription control, high-level dashboards, trusts AI summaries over digging into raw data |
| **Accountant / Finance User** | In-house bookkeeper or finance lead | GL, AR/AP, compliance filings, bank reconciliation, financial reporting |
| **External Accountant (Mali Müşavir)** | Third-party accountant serving multiple client companies | Needs cross-tenant-safe access to their assigned clients only, e-Beyanname submission tooling, exportable ledgers |
| **Purchasing Officer** | Manages vendors and purchase orders | PO creation/approval, vendor comparison, budget checks |
| **Warehouse / Inventory Staff** | Handles stock movements | Barcode scanning, stock counts, transfer/receiving workflows, ideally mobile-friendly |
| **Production Planner** | Manufacturing scheduling | BOM management, work order scheduling, capacity view |
| **Sales / CRM User** | Manages leads, quotes, orders | Pipeline view, quote generation, order status |
| **HR / Payroll Admin** | Manages employee records and payroll | Payroll runs, SGK submission, leave management |
| **Project Manager** | Runs internal or client projects | Time tracking, project costing, budget vs. actual |
| **POS / Retail Cashier** | Front-of-store sales staff | Fast checkout, offline resilience, minimal training needed |
| **IT / System Administrator** | Configures the tenant | User/role management, integrations, audit log review |
| **AI Assistant (system actor)** | Not a human, but must be modeled as a scoped actor | Every AI action is attributable to the human who triggered it plus the AI itself, for audit purposes |

Every functional requirement below should be read as "the relevant role(s) must be able to..." — role-specific access is a permissions concern (see `REQ-CORE-PERM-*`), not a reason to duplicate requirements per role.

---

## 4. Functional Requirements — Core Platform

The Core Platform is included in every subscription tier and every package depends on it. No package may be purchased standalone without Core.

### 4.1 Identity, Users, Roles & Permissions

- **REQ-CORE-USR-001**: The system must support creating, deactivating, and deleting user accounts within a tenant, with email-based invitation flow.
- **REQ-CORE-USR-002**: The system must support role-based access control (RBAC) with a set of built-in roles (see §3) and the ability to define custom roles with granular permissions per module/action (view, create, edit, delete, approve, export).
- **REQ-CORE-USR-003**: The system must support field-level permission restrictions for sensitive data (e.g., an Inventory user can see stock counts but not unit cost if that field is restricted; a manager can see salary fields in HR that a regular employee cannot).
- **REQ-CORE-USR-004**: The system must support multi-factor authentication (MFA) as an option per tenant, and mandatory for Enterprise tier.
- **REQ-CORE-USR-005**: The system must support Single Sign-On (SSO/SAML or OIDC) for Enterprise tier.
- **REQ-CORE-USR-006**: The system must support scoping an external accountant's access to only the specific tenant(s) they've been granted access to, with the ability for the accountant to switch between clients without separate logins.
- **REQ-CORE-USR-007**: All permission checks that apply to a human user acting through the UI must apply identically when the AI assistant acts on that user's behalf (no privilege escalation via AI).
- **REQ-CORE-USR-008**: The system must support session management: forced logout, active session listing, and session revocation by an admin.

### 4.2 General Ledger & Chart of Accounts

- **REQ-CORE-GL-001**: The system must provide a configurable Chart of Accounts (COA), with starter templates appropriate for Turkish statutory accounting (Tekdüzen Hesap Planı) as well as generic/international templates.
- **REQ-CORE-GL-002**: The system must support double-entry bookkeeping with journal entries, automatic balancing validation, and posting/draft states.
- **REQ-CORE-GL-003**: The system must support multi-currency accounting: transactions in a foreign currency, automatic conversion to functional currency using configurable exchange rate sources, and realized/unrealized FX gain-loss tracking.
- **REQ-CORE-GL-004**: The system must support multi-entity / multi-company structures with the ability to consolidate financials across entities (Professional tier and above).
- **REQ-CORE-GL-005**: The system must support period close (month-end/year-end) with a lock mechanism preventing edits to closed periods, and a defined re-open/adjustment workflow.
- **REQ-CORE-GL-006**: The system must generate standard financial statements: Balance Sheet, Income Statement (P&L), Cash Flow Statement, and Trial Balance, in both Turkish statutory format and a generic/IFRS-friendly format.
- **REQ-CORE-GL-007**: The system must support recurring/template journal entries (e.g., monthly depreciation, accruals).
- **REQ-CORE-GL-008**: The system must maintain a complete, immutable transaction history for every ledger entry (who posted it, when, from what source document).

### 4.3 Accounts Receivable / Accounts Payable

- **REQ-CORE-AR-001**: The system must support customer invoice creation, from both manual entry and auto-generation from sales orders (if the Sales package is active).
- **REQ-CORE-AR-002**: The system must track invoice status (draft, sent, partially paid, paid, overdue, cancelled) and support partial payments.
- **REQ-CORE-AR-003**: The system must support AR aging reports (30/60/90+ day buckets) and automated overdue-payment reminders (email).
- **REQ-CORE-AP-001**: The system must support vendor bill entry, from both manual entry and auto-generation from purchase orders (if the Purchasing package is active).
- **REQ-CORE-AP-002**: The system must support AP aging, payment scheduling, and batch payment runs.
- **REQ-CORE-AR-AP-001**: The system must support bank statement import (CSV/OFX/MT940 or direct bank API where available) and AI-assisted reconciliation matching invoices/bills to bank transactions (see §7 for AI-specific requirements on this).

### 4.4 AI Chat & Query Layer (Core)

This is a Core capability, embedded in every tier — see `product.md` §4 for the product rationale.

- **REQ-CORE-AI-001**: Every screen in the application must expose a persistent, openable right-side panel providing a conversational AI assistant.
- **REQ-CORE-AI-002**: The AI assistant must be able to answer natural-language questions across every module/package the tenant has purchased (e.g., "which vendors do we owe the most right now," "what's our gross margin this quarter vs last," "show late purchase orders from last month").
- **REQ-CORE-AI-003**: The AI assistant's answers to data questions must be traceable back to the underlying records (drill-down/citation), never presented as an unverifiable assertion.
- **REQ-CORE-AI-004**: The AI assistant must only retrieve/act on data the requesting user is already permitted to see or do through the normal UI (no privileged AI service account) — see `REQ-CORE-USR-007`.
- **REQ-CORE-AI-005**: The AI assistant must be able to explain any record, workflow, or report field in plain language on request (e.g., "what does this reconciliation flag mean").
- **REQ-CORE-AI-006**: The AI assistant must support both Turkish and English conversation, matching the user's chosen interface language, and must handle Turkish financial/business terminology correctly (not literal machine translation).
- **REQ-CORE-AI-007**: The AI assistant must be able to take mutating actions (e.g., create a purchase order, post a journal entry) only after presenting a clear preview and receiving explicit user confirmation, for any action above a configurable risk/value threshold (see `REQ-CORE-AI-010`).
- **REQ-CORE-AI-008**: Every AI-initiated action (read or write) must be logged in an audit trail capturing the request, the data/tools used, and any human approval — see `REQ-CORE-AUDIT-003`.
- **REQ-CORE-AI-009**: The AI assistant must degrade gracefully and say "I don't know" or "I can't verify this" rather than presenting a fabricated number, especially for financial figures.
- **REQ-CORE-AI-010**: Each tenant/admin must be able to configure the auto-approve vs. requires-confirmation threshold for AI-initiated write actions (e.g., dollar/TRY value limits per action type).
- **REQ-CORE-AI-011**: The system must track AI usage (query volume, action volume) per tenant for the metered "AI Action credit" billing model described in `product.md` §7.

### 4.5 Compliance & Localization Engine

- **REQ-CORE-LOC-001**: The system must support a pluggable localization/compliance layer so that country-specific tax, legal, and e-government requirements can be added without modifying Core.
- **REQ-CORE-LOC-002**: The system must support per-tenant configuration of applicable tax regime, statutory reporting calendar, and currency.
- **REQ-CORE-LOC-003**: Turkey must be the first fully implemented localization (see §6 for detailed Turkey requirements).

### 4.6 Audit Trail & Logging

- **REQ-CORE-AUDIT-001**: The system must log every create/update/delete action on financial and compliance-relevant records, capturing who, when, what changed (before/after values), and from where (UI, API, AI).
- **REQ-CORE-AUDIT-002**: Audit logs must be append-only (no user, including admins, can edit or delete audit history) and exportable for external audit purposes.
- **REQ-CORE-AUDIT-003**: AI-specific audit logs must additionally capture: the user's original request/prompt, the data/context retrieved to answer it, any tool/action calls made, and the approval/rejection decision if applicable.
- **REQ-CORE-AUDIT-004**: Audit logs must be retained for a configurable period meeting Turkish statutory record-keeping requirements (minimum 5 years for accounting records under Turkish Commercial Code / Tax Procedure Law) and exportable in a regulator-acceptable format.

### 4.7 Base Reporting & Dashboards

- **REQ-CORE-RPT-001**: The system must provide a configurable home dashboard per role, showing the most relevant KPIs (e.g., cash position for Finance, overdue POs for Purchasing).
- **REQ-CORE-RPT-002**: The system must support exporting any report/table view to PDF, Excel (XLSX), and CSV.
- **REQ-CORE-RPT-003**: The system must support scheduled report delivery via email (e.g., a weekly cash-flow summary sent every Monday).

### 4.8 Multi-currency & Multi-entity

- **REQ-CORE-ENT-001**: The system must support a tenant operating multiple legal entities/companies under one subscription, each with its own COA, ledgers, and statutory filings, while allowing consolidated reporting (Professional tier+).
- **REQ-CORE-ENT-002**: The system must support intercompany transactions with automatic elimination in consolidated reports.

### 4.9 Notifications

- **REQ-CORE-NOTIF-001**: The system must support in-app and email notifications for key events (approval requests, overdue items, AI action pending approval, compliance filing deadlines).
- **REQ-CORE-NOTIF-002**: Users must be able to configure their own notification preferences per event type and channel.

### 4.10 Document Management / Attachments

- **REQ-CORE-DOC-001**: The system must allow attaching files (invoices, contracts, receipts, images) to any relevant record, with a preview capability for common formats (PDF, images).
- **REQ-CORE-DOC-002**: Uploaded documents must be scannable by the AI assistant for OCR-based data extraction (e.g., pulling vendor/amount/date from a scanned receipt) where the relevant package supports it.

### 4.11 Configurable Data Views

Added from direct user feedback (`docs/feedback.md` "Feedback 1") — every data-table-heavy screen across every package should behave consistently, so this lives in Core rather than being reimplemented per package.

- **REQ-CORE-UX-001**: Every screen presenting tabular data must let the user reorder columns (drag), show/hide individual columns, and resize column widths.
- **REQ-CORE-UX-002**: Every such screen must support per-column sorting (ascending/descending) and per-column filtering.
- **REQ-CORE-UX-003**: A user must be able to save a screen's current column configuration (order, visibility, widths, sort, filters) as a named "view," mark it personal (visible only to them) or shared (visible to every user on the tenant), and switch between saved views for that screen. Editing a shared view is restricted to its creator (no view-level ACL beyond that in this pass).
- **REQ-CORE-UX-004**: Editable fields on a data-table screen must support inline, spreadsheet-style editing (click/double-click a cell to edit in place) rather than requiring navigation to a separate edit form, where the underlying field is safely editable inline (not every field on every screen needs this — e.g. computed/read-only columns don't).
- **REQ-CORE-UX-005**: The primary navigation must group related screens under collapsible section headers rather than a single flat list, so the number of visible items scales with how many packages a tenant has active without becoming unreadable.

---

## 5. Functional Requirements — Packages

Each package builds on Core and is independently priced/purchasable. Package-internal AI capability (agentic automation) is metered per `product.md` §4/§7; the base AI chat's awareness of a package's data is included automatically once the package is active.

### 5.1 Purchasing / Procurement

- **REQ-PUR-001**: Create, edit, and track purchase orders (PO) through their lifecycle (draft, sent, partially received, received, closed, cancelled).
- **REQ-PUR-002**: Support configurable multi-level approval workflows for POs above defined value thresholds.
- **REQ-PUR-003**: Maintain a vendor master record (contact info, payment terms, tax ID, historical pricing).
- **REQ-PUR-004**: Support vendor price comparison across historical POs for the same item.
- **REQ-PUR-005**: Auto-generate vendor bills (AP) from received POs, with three-way match (PO / receipt / bill) validation.
- **REQ-PUR-006**: Support requisition requests from other departments that route into the purchasing approval workflow.
- **REQ-PUR-007**: The AI assistant must be able to draft a PO from an unstructured input (e.g., a forwarded supplier email or a natural-language request) for user review before submission.

### 5.2 Inventory & Warehouse Management

- **REQ-INV-001**: Maintain item/product master data (SKU, description, unit of measure, cost method — FIFO/weighted average).
- **REQ-INV-002**: Support multi-warehouse/multi-location stock tracking with transfer workflows between locations.
- **REQ-INV-003**: Support barcode scanning for receiving, picking, and stock counts, from a mobile-friendly interface.
- **REQ-INV-004**: Support cycle counting and full physical inventory workflows with variance reporting.
- **REQ-INV-005**: Support stock reservation (allocating stock to a sales order before shipment).
- **REQ-INV-006**: Provide low-stock/reorder-point alerts, with AI-assisted reorder quantity suggestions based on historical consumption.
- **REQ-INV-007**: Support lot/batch and serial number tracking for items requiring traceability.
- **REQ-INV-008**: Support landed cost allocation (freight, customs, duties) onto received inventory.

### 5.3 Manufacturing / Production (MRP)

- **REQ-MFG-001**: Support Bill of Materials (BOM) definition, including multi-level/nested BOMs.
- **REQ-MFG-002**: Support work order creation, scheduling, and tracking through production stages.
- **REQ-MFG-003**: Support Material Requirements Planning (MRP) — calculating required raw materials/components based on demand and current stock, generating suggested purchase/production orders.
- **REQ-MFG-004**: Support capacity planning against defined work centers/machines/labor resources.
- **REQ-MFG-005**: Support production cost tracking (materials, labor, overhead) rolling up to finished-good cost.
- **REQ-MFG-006**: Support quality control checkpoints within a work order (pass/fail/rework recording).
- **REQ-MFG-007**: The AI assistant must be able to explain production variances (e.g., "why did the cost of Work Order #1234 exceed the standard cost") by tracing component and labor cost inputs.

### 5.4 Sales & CRM

- **REQ-CRM-001**: Support lead and opportunity tracking through a configurable pipeline.
- **REQ-CRM-002**: Support quote/proposal generation with configurable templates, converting to a sales order on acceptance.
- **REQ-CRM-003**: Support sales order management through to invoicing and fulfillment, integrating with Inventory (if active) for stock allocation.
- **REQ-CRM-004**: Support customer master data with interaction history (calls, emails, meetings logged).
- **REQ-CRM-005**: Support sales performance reporting (by rep, by product, by region, by period).
- **REQ-CRM-006**: The AI assistant must be able to draft a follow-up email or quote based on a natural-language instruction and the customer's history.

### 5.5 HR & Payroll (Turkey-aware)

- **REQ-HR-001**: Maintain employee master records (personal info, employment contract details, position, department).
- **REQ-HR-002**: Support leave management (annual leave, sick leave) with configurable Turkish statutory leave entitlement rules.
- **REQ-HR-003**: Support payroll calculation compliant with Turkish statutory requirements (gross-to-net, SGK premium calculation, income tax withholding, stamp duty).
- **REQ-HR-004**: Support monthly SGK e-Bildirge submission (see `REQ-LOC-TR-006`).
- **REQ-HR-005**: Support payslip generation and secure distribution to employees.
- **REQ-HR-006**: Support basic performance review / goal tracking (lower priority than payroll compliance — see `development-plan.md` for phasing).
- **REQ-HR-007**: The AI assistant must be able to answer employee-facing questions about their own leave balance/payslip without exposing other employees' data (permission-scoped).

### 5.6 Project Management

- **REQ-PRJ-001**: Support project creation with budget, timeline, and task breakdown.
- **REQ-PRJ-002**: Support time tracking against projects/tasks, by employee.
- **REQ-PRJ-003**: Support project costing (labor + materials + expenses) and budget-vs-actual reporting.
- **REQ-PRJ-004**: Support client billing based on tracked time/milestones (professional services automation use case).

### 5.7 POS / Retail

- **REQ-POS-001**: Support point-of-sale checkout: item scan/lookup, discounts, multiple payment methods (cash, card, split).
- **REQ-POS-002**: Support multi-store/multi-till configurations reporting into central Inventory and GL.
- **REQ-POS-003**: Integrate with fiscal payment devices/printers as required by Turkish tax regulations (yeni nesil ödeme kaydedici cihaz / fiscal printer integration).
- **REQ-POS-004**: Support daily Z-report (end-of-day sales/cash reconciliation).
- **REQ-POS-005**: Support returns/exchanges at POS with automatic inventory and GL impact.
- **REQ-POS-006**: Support loyalty/discount program configuration.
- **REQ-POS-007**: Auto-generate e-Arşiv invoices/fiscal receipts from POS transactions per Turkish requirements.
- **REQ-POS-008**: The POS interface must remain operable (queue-and-sync) during short internet outages, with automatic reconciliation once connectivity is restored.

### 5.8 E-commerce Integration

- **REQ-ECOM-001**: Support order/inventory sync with major marketplaces relevant to Turkey (e.g., Trendyol, Hepsiburada) and general platforms (e.g., Shopify), where a public integration API exists.
- **REQ-ECOM-002**: Auto-generate e-Arşiv invoices for e-commerce/B2C orders per the lower revenue threshold that applies to e-commerce sellers (see `REQ-LOC-TR-002`).
- **REQ-ECOM-003**: Support automatic stock-level sync back to marketplaces to prevent overselling.

### 5.9 Advanced BI / Analytics

- **REQ-BI-001**: Support a self-service report/dashboard builder (drag-and-drop dimensions/metrics) beyond the base reports included in Core.
- **REQ-BI-002**: Support the AI assistant generating a new chart/dashboard from a natural-language request (e.g., "show me monthly revenue by product category for the last 12 months"), grounded in the semantic/metrics layer (not free-form SQL — see `technical.md`).
- **REQ-BI-003**: Support saved/shared custom reports across the organization with permission scoping.
- **REQ-BI-004**: Support anomaly detection surfaced proactively (e.g., "this vendor's invoice is 40% higher than their historical average — review before approving").

### 5.10 Advanced AI Agents Pack

- **REQ-AIAGENT-001**: Support tenant-configurable autonomous agents that perform scheduled or trigger-based multi-step workflows (e.g., a daily reconciliation sweep, a weekly reorder-suggestion agent) within the human-in-the-loop guardrails defined in `REQ-CORE-AI-007/010`.
- **REQ-AIAGENT-002**: Provide a low-code interface for an admin to define a new custom agent (trigger, allowed tools, approval threshold) without engineering involvement.
- **REQ-AIAGENT-003**: Provide a dashboard showing agent activity, actions taken, actions pending approval, and quantified time/cost saved.

---

## 6. Turkey Localization Requirements

These requirements are **non-negotiable for any Turkish customer** — see `product.md` §3.4 for why this is treated as an existential (not optional) requirement.

- **REQ-LOC-TR-001**: The system must generate, sign, and transmit **e-Fatura** invoices per GİB (Gelir İdaresi Başkanlığı) specifications for any tenant whose revenue crosses the statutory threshold (currently TRY 3M general threshold; lower thresholds apply to specific sectors — thresholds must be kept configurable/updatable as GİB communiqués change them, not hardcoded).
- **REQ-LOC-TR-002**: The system must generate **e-Arşiv Fatura** for B2C or non-e-Fatura-registered counterparties, including the lower thresholds applicable to e-commerce and real estate sectors, and the no-threshold requirement for hotels/accommodation.
- **REQ-LOC-TR-003**: The system must generate **e-Defter** (electronic ledger — yevmiye defteri / kebir defteri) in the GİB-required format (berat + XBRL-GL) for any tenant on e-Fatura keeping accrual-basis books.
- **REQ-LOC-TR-004**: The system must generate **e-İrsaliye** (e-waybill) for tenants meeting the applicable revenue threshold.
- **REQ-LOC-TR-005**: The system must support **e-Müstahsil Makbuzu** (producer receipt) for tenants purchasing from tax-exempt farmers or registered with the Hal Kayıt Sistemi, and must support GİB's ability to force any tenant into this requirement via risk-based notification regardless of turnover.
- **REQ-LOC-TR-006**: The system must generate and submit **e-Bildirge** (monthly SGK payroll/premium declaration) for any tenant with employees.
- **REQ-LOC-TR-007**: The system must support **KDV (VAT) beyannamesi** and related declarations (Muhtasar, Damga Vergisi, Kurumlar Vergisi) generation, and — where the tenant's accountant is enrolled — direct submission via the GİB e-Beyan web-service integration.
- **REQ-LOC-TR-008**: All Turkish compliance documents/filings must be retrievable and re-exportable for a minimum 5-year statutory retention window.
- **REQ-LOC-TR-009**: The system must maintain a process (not just a one-time build) for tracking and implementing GİB Tebliğ (communiqué) changes to thresholds, formats, and required fields on an ongoing basis — this is a permanent operational requirement, not a project milestone (see `development-plan.md` §9).
- **REQ-LOC-TR-010**: The system must integrate with GİB either directly (as a certified özel entegratör) or via a partner özel entegratör — this is a build-vs-partner decision to be resolved in `technical.md`, but the customer-facing requirement is that filings are transmitted correctly and on time regardless of which path is chosen.
- **REQ-LOC-TR-011**: The system must support Turkish fiscal payment device integration for POS (see `REQ-POS-003`).

---

## 7. AI-Specific Requirements (Cross-Cutting)

These apply across every module wherever the AI assistant touches that module's data — restated here as a consolidated checklist so nothing is missed when a new package is designed.

- **REQ-AI-XCUT-001**: The AI must never compute a financial figure by free-form generation — every number must trace to a deterministic calculation over real records (see `technical.md` for the semantic-layer architecture that enforces this).
- **REQ-AI-XCUT-002**: The AI must never access data outside the requesting user's existing permissions, under any circumstance, including via document/RAG retrieval.
- **REQ-AI-XCUT-003**: Any AI-suggested action that would modify data must be clearly distinguished in the UI from an already-completed action, and must require explicit confirmation above the tenant-configured threshold.
- **REQ-AI-XCUT-004**: The AI must log a complete, human-readable audit trail for every interaction (see `REQ-CORE-AUDIT-003`).
- **REQ-AI-XCUT-005**: The AI must clearly indicate uncertainty rather than presenting a guess with false confidence, particularly for compliance-relevant answers (e.g., "am I required to file e-İrsaliye").
- **REQ-AI-XCUT-006**: The AI must support both Turkish and English queries interchangeably within the same conversation.
- **REQ-AI-XCUT-007**: AI response latency for a standard data question must meet the performance target in `REQ-NFR-PERF-004`.

---

## 8. Non-Functional Requirements

### 8.1 Performance
- **REQ-NFR-PERF-001**: Standard page loads must complete within 2 seconds under normal load (p95).
- **REQ-NFR-PERF-002**: Report generation for standard reports (e.g., monthly P&L) must complete within 5 seconds for a tenant with up to 100,000 transactions/year.
- **REQ-NFR-PERF-003**: The system must support at least 500 concurrent users per mid-size tenant without degradation.
- **REQ-NFR-PERF-004**: AI chat responses to a standard data question must begin streaming a response within 3 seconds and complete within 10 seconds for typical queries.

### 8.2 Scalability
- **REQ-NFR-SCALE-001**: The system architecture must support scaling from a 1-user Starter tenant to a multi-thousand-user Enterprise tenant without a re-architecture.
- **REQ-NFR-SCALE-002**: The system must support tenant growth (data volume, user count) without requiring migration to a different product tier at the infrastructure level (tier differences are feature/package gating, not different codebases).

### 8.3 Availability & Reliability
- **REQ-NFR-AVAIL-001**: The system must target 99.9% uptime for Growth tier and above, with a published status page.
- **REQ-NFR-AVAIL-002**: The system must perform automated daily backups with a defined Recovery Point Objective (RPO ≤ 24h) and Recovery Time Objective (RTO ≤ 4h), tested periodically.
- **REQ-NFR-AVAIL-003**: Compliance-critical functions (e-Fatura/e-Arşiv generation) must have a documented fallback procedure if the GİB service itself is unavailable, consistent with GİB's own grace-period rules.

### 8.4 Security
- **REQ-NFR-SEC-001**: All data in transit must be encrypted (TLS 1.2+).
- **REQ-NFR-SEC-002**: All sensitive data at rest (financial records, personal data, payroll) must be encrypted.
- **REQ-NFR-SEC-003**: The system must undergo a security review/penetration test before each major release and at least annually.
- **REQ-NFR-SEC-004**: The system must comply with Turkish KVKK (Kişisel Verilerin Korunması Kanunu) requirements for personal data handling, including data subject access/deletion requests.
- **REQ-NFR-SEC-005**: The system must comply with GDPR for any customer/user data belonging to EU-resident individuals, if/when the product expands beyond Turkey.
- **REQ-NFR-SEC-006**: Tenant data must be logically isolated such that no tenant can access another tenant's data under any application-level bug or misconfiguration (defense in depth, not reliance on a single check).
- **REQ-NFR-SEC-007**: The system must support configurable password policies and account lockout after repeated failed login attempts.
- **REQ-NFR-SEC-008**: Financial data relevant to Turkish statutory bookkeeping must, at minimum, comply with any data-residency requirements applicable under Turkish law.
- **REQ-NFR-SEC-009**: The system must maintain a responsible disclosure / bug bounty channel for security researchers.
- **REQ-NFR-SEC-010**: Enterprise tier must support dedicated/isolated infrastructure or VPC deployment options for customers with heightened data-isolation requirements.

### 8.5 Localization & Accessibility
- **REQ-NFR-I18N-001**: All UI text, validation messages, generated documents (invoices, reports), and AI responses must be available in Turkish and English, switchable per user.
- **REQ-NFR-I18N-002**: Date, number, and currency formatting must follow the conventions of the selected locale (e.g., Turkish decimal comma vs. English decimal point).
- **REQ-NFR-A11Y-001**: The application must meet WCAG 2.1 AA accessibility standards for core workflows.

### 8.6 Browser & Device Support
- **REQ-NFR-DEV-001**: The application must support the current and prior major versions of Chrome, Edge, Firefox, and Safari.
- **REQ-NFR-DEV-002**: Core workflows (approvals, dashboards, AI chat) must be usable on tablet-sized screens; POS and Warehouse/Inventory scanning workflows must be optimized for mobile/handheld use.

---

## 9. Integration Requirements

- **REQ-INT-001**: Direct or partner-mediated integration with GİB e-Devlet services for all filings listed in §6.
- **REQ-INT-002**: Bank statement import (minimum: CSV/MT940; ideal: direct open-banking API where Turkish banks support it).
- **REQ-INT-003**: Payment gateway integration for online payment collection (e.g., iyzico, Param, or equivalent Turkish PSPs) where the Sales/E-commerce package is active.
- **REQ-INT-004**: E-commerce marketplace integrations as listed in `REQ-ECOM-001`.
- **REQ-INT-005**: Email/SMS provider integration for notifications and customer-facing communications (invoices, payslips).
- **REQ-INT-006**: Support for data export/import in formats compatible with common Turkish legacy systems (Logo, Netsis, Mikro) to ease migration — see §10.
- **REQ-INT-007**: A public API (documented, versioned) must be available for Enterprise-tier customers to build custom integrations.

---

## 10. Data Migration & Legacy System Integration Requirements

**This is a priority requirements area, not a nice-to-have.** Almost every prospective customer already runs something — Logo, Netsis, Mikro, a mix of Excel and paper, or (for larger prospects) SAP Business One — and per `product.md` §2 (pillar 6), fear of losing historical data or breaking compliance continuity during a switch is the single biggest reason customers stay on a product they otherwise dislike. Migration tooling must be a supported, repeatable, demoable product feature included with every subscription — not a bespoke consulting engagement quoted per customer, and not an afterthought scoped in late. It must cover two distinct paths: **(a) direct integration/connectors** against a source system's own database or export format, and **(b) generic database/file export import** for anything not directly supported. See `technical.md` §9 for the architecture that implements this.

- **REQ-DATA-001**: The system must support importing Chart of Accounts, customer/vendor master data, item master data, and opening balances from spreadsheet templates (XLSX/CSV) with validation and error reporting.
- **REQ-DATA-002**: The system must support a guided migration assistant (AI-assisted where possible) for customers migrating from Logo, Netsis, or Mikro, mapping their existing COA and master data into the new system.
- **REQ-DATA-003**: The system must validate imported data against Turkish tax ID (VKN/TCKN) checksum rules and flag invalid records rather than silently accepting them.
- **REQ-DATA-004**: The system must allow a customer to export their full data (all modules) in a portable format at any time, including on subscription cancellation (data portability).
- **REQ-DATA-005**: The system must provide a direct import connector for **Logo** products (Tiger/GO/j-Platform/Netsis family) capable of reading a structured database export or backup provided by the customer or their reseller, extracting COA, customer/vendor master data, item master data, open AR/AP balances, and — where feasible — historical transaction detail (not opening balances alone).
- **REQ-DATA-006**: The system must provide an equivalent direct import connector for **Mikro Yazılım** (Run/Jump/Fly product lines), covering the same data categories as `REQ-DATA-005`.
- **REQ-DATA-007**: The system must provide a **generic database import path** (a defined, documented schema/CSV specification) for any source system without a dedicated connector, so migration is never a hard blocker even for less common or heavily customized legacy installs — this is the fallback for anything outside the versioned connector set described in `product.md` §10 (Risks).
- **REQ-DATA-008**: For every import path, the system must offer **AI-assisted field and account mapping** — proposing a mapping between the source system's chart of accounts/master data and the new system's schema, with the customer (or their accountant) reviewing and confirming every proposed mapping before it is applied. The AI must never silently auto-commit a mapping for financially significant fields.
- **REQ-DATA-009**: Every migration must produce a **dry-run / preview report** before any data is committed to production: record counts found, proposed mappings, flagged errors (invalid tax IDs, unbalanced historical entries, duplicate customer/vendor records), and an explicit list of anything the system could not confidently map and needs human input on.
- **REQ-DATA-010**: The system must support a **parallel-run / reconciliation period**: after data is imported, the customer must be able to compare key totals (trial balance, AR/AP aging, stock-on-hand) between the new system and their legacy system for a transition window, to build confidence before fully cutting over.
- **REQ-DATA-011**: Migration must support importing **historical transaction detail**, not just opening balances, to the extent the source data allows — so a customer doesn't lose the ability to run trend/comparison reports against prior periods immediately after switching.
- **REQ-DATA-012**: The system must provide a **migration progress dashboard** visible to the customer (and any implementation partner) showing what has been imported, what is pending review, and what has been confirmed/committed.
- **REQ-DATA-013**: A migration must be **reversible/undoable** up until the customer explicitly confirms go-live — an in-progress or previewed migration must never irreversibly alter production data before that confirmation.
- **REQ-DATA-014**: Legacy data handled during migration (which may include a full database export/backup of the customer's prior system) must be encrypted in transit and at rest, retained only as long as needed to complete and validate the migration, and deleted or archived per a documented retention policy afterward — this data is often more sensitive than the new system's own baseline (it may contain full historical financial and personal data from another vendor's system).
- **REQ-DATA-015**: Where a source system runs on-premise with no exposed API (the common case for older Logo/Netsis/Mikro installs), the system must provide a **customer-run export tool** the customer or their IT/reseller can execute locally against their own database to produce an import bundle, rather than requiring inbound network access into the customer's environment — see `technical.md` §9.3 for the mechanism.
- **REQ-DATA-016**: The migration/onboarding experience must be usable by a non-technical accountant or business owner for the common case (spreadsheet or connector-based import for a small business), while still supporting a more hands-on, partner/reseller-assisted flow for larger or messier migrations — it should not require the customer to be technical to complete a standard migration.

---

## 11. Reporting Requirements

- **REQ-RPT-GEN-001**: Every package must ship with a defined set of standard reports relevant to that function (see package sections above for specifics), in addition to the Core financial statements.
- **REQ-RPT-GEN-002**: All reports must be filterable by date range, entity (if multi-entity), and relevant dimensions (e.g., by warehouse, by sales rep).
- **REQ-RPT-GEN-003**: All standard reports must be reproducible identically by both the deterministic reporting engine and by asking the AI assistant for the same information in natural language (consistency requirement — see `REQ-AI-XCUT-001`).

---

## 12. Acceptance Criteria & Definition of Done (General)

A requirement is considered met when:
1. The functionality is implemented and covered by automated tests (unit + integration as appropriate).
2. For Turkey compliance requirements specifically: the output has been validated against the current GİB schema/test environment, not just internally.
3. For AI requirements specifically: the behavior has been validated against a golden-query/eval test set, not just spot-checked manually.
4. The relevant user-facing text exists in both Turkish and English.
5. The feature respects the permission model (tested with at least one role that should be denied access).
6. Documentation (in-app help + AI assistant awareness of the feature) is updated.

---

## 13. Out of Scope (for the requirements set as currently defined)

- Non-Turkish country localizations (future phase, not detailed here — see `product.md` §9 Phase 3+).
- On-premise (non-cloud) deployment, except as a possible Enterprise-tier dedicated-infrastructure variant (`REQ-NFR-SEC-010`), which is still cloud-hosted, not customer-datacenter-hosted.
- Native mobile apps (a responsive web app is required per §8.6; dedicated iOS/Android apps are a future consideration).
- Industry-specific verticals beyond general manufacturing/retail/services (e.g., healthcare-specific or construction-specific modules) are out of scope until explicitly prioritized.

---

## 14. Glossary

| Term | Meaning |
|---|---|
| **GİB** | Gelir İdaresi Başkanlığı — Turkish Revenue Administration |
| **e-Fatura / e-Arşiv / e-Defter / e-İrsaliye** | Turkish mandatory electronic invoice / archive invoice / ledger / waybill formats |
| **SGK** | Sosyal Güvenlik Kurumu — Turkish Social Security Institution |
| **KVKK** | Kişisel Verilerin Korunması Kanunu — Turkish Personal Data Protection Law (GDPR analogue) |
| **Özel Entegratör** | GİB-certified private integrator authorized to transmit e-transformation documents on behalf of taxpayers |
| **Mali Müşavir** | Certified public accountant / financial advisor, common external role for Turkish SMEs |
| **COA** | Chart of Accounts |
| **BOM** | Bill of Materials |
| **MRP** | Material Requirements Planning |
| **RBAC** | Role-Based Access Control |
| **Tenant** | A single customer organization's isolated instance of data within the multi-tenant platform |
