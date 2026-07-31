# Product Strategy — AI-Native ERP Platform

**Status:** Draft v1 — living document, meant to be iterated on
**Last updated:** 2026-07-31
**Owner:** Cüneyt

---

## 0. How to read this document

This is a first comprehensive pass covering market analysis, product scope, packaging, pricing, and go-to-market. It is long on purpose — this is a big, multi-year product and the goal is to have one place that captures the thesis, the competitive facts we've gathered, and the open decisions. Sections marked **[DECISION NEEDED]** are places where I've made a reasonable default call but you should explicitly confirm or override it. Sections marked **[RESEARCH GAP]** are things we could not find hard data on and would need direct outreach (e.g., a Turkish ERP consulting firm) to nail down.

Confidence levels are noted inline where relevant — this market (especially the Turkish side) does not publish clean price lists, so some figures are aggregator-sourced estimates, not vendor-confirmed.

---

## 1. Executive Summary

SAP and legacy ERP vendors sell two things beyond software: **complexity** and **dependency**. The complexity justifies armies of consultants at $150–$2,500/day; the dependency (proprietary data models, custom ABAP code, multi-year upgrade cycles) locks customers in once they've paid the initial $500K–$20M implementation bill. Logo Yazılım, the dominant ERP vendor in Turkey, avoids SAP's price tag but inherits a version of the same problem at SMB scale: dated UX, unreliable cloud infrastructure, opaque reseller-quoted pricing, and a support experience customers openly complain about — yet it wins because it does the one thing that's non-negotiable in Turkey (GİB e-transformation compliance: e-Fatura, e-Arşiv, e-Defter, e-İrsaliye) reliably enough, and because the entire accountant/consultant ecosystem already knows it.

The opening we're targeting: **ERP AI is currently bolted onto 20-40 year old data architectures.** SAP's Joule, Microsoft's Copilot, and Oracle's Fusion AI Agents are all real and improving fast, but they were retrofitted onto S/4HANA, Dataverse, and Fusion Cloud schemas designed long before LLMs existed. A wave of well-funded startups (Rillet, DualEntry, Campfire, Light, Everest — collectively raising $400M+ in the last 18 months) is betting that an AI-native rebuild wins the next generation of mid-market ERP. None of them are focused on Turkey, and none of them have solved (or attempted) Turkish e-Devlet compliance.

**Our thesis:** build an ERP that is AI-native from the data model up (not a chatbot bolted onto SQL tables), sold as a modular core + packages (so a 10-person company pays for 10% of what a 500-person company pays, not "contact sales"), compliance-first for Turkey from day one (this is existential, not a nice-to-have), and priced transparently — a structural contrast to a market where "contact your reseller for a quote" is the norm.

**Primary market:** Turkey, entering at the underserved end (76%+ of 10-49 employee firms have *no ERP at all* per TÜİK 2025 data) rather than fighting Logo head-on for its existing enterprise accounts on day one. **Secondary market:** English-speaking SMB/mid-market globally, competing in the same "AI-native ERP" category as Rillet/DualEntry but with broader operational scope (not finance-only) and a modular pricing model closer to Odoo's than NetSuite's.

---

## 2. Vision & Product Thesis

1. **AI is infrastructure, not a feature.** Every screen, every workflow, every record has an AI layer that can explain it, query across it, and (with permission and confirmation) act on it. This is the default architecture, not an upsell.
2. **Modular by design, not by accident.** A company buys a Core (accounting, users, permissions, AI layer, compliance engine) and adds Packages (Purchasing, Inventory, Manufacturing, HR, CRM, POS...) as they need them — each package is a real product boundary, independently priced, independently team-owned, but sharing one data model and one AI layer.
3. **Compliance is a platform capability, not a bolt-on.** Country-specific legal/tax/e-government requirements (starting with Turkey) are modeled as a pluggable "Localization Pack" layer that the core is built to support from day one — not retrofitted later like most vendors do when they expand geographies.
4. **Transparent, predictable pricing.** Every tier and package has a public price. This is a direct contrast to both SAP (opaque, 50%+ negotiation swings) and Logo/Turkish vendors (reseller-quoted, "contact a partner").
5. **Fast time-to-value.** Legacy ERP implementations run 6 months to multiple years. AI-native competitors (Rillet) market 4-week implementations. We should target the same order of magnitude for Core + 1-2 packages, using AI itself to accelerate data migration, chart-of-accounts setup, and configuration (this is a real product feature, not just a services efficiency).
6. **Migration is a first-class product capability, not a professional-services afterthought.** Nearly every prospective customer already runs something — Logo, Netsis, Mikro, Excel, or a mix — and the single biggest reason SMEs stay on a product they openly complain about is fear of losing historical data or breaking compliance continuity during a switch. Importing a company's existing data (via direct legacy-system connectors where feasible, or structured database/file exports where not) must be a built, supported, repeatable product feature from day one, not a bespoke consulting engagement quoted per customer. This directly attacks Logo's stickiest form of lock-in — switching cost — the same way transparent pricing attacks its opaque quoting.

---

## 3. Market Analysis

### 3.1 Global ERP Landscape

| Vendor | Target segment | Pricing model | Approx. cost | AI copilot | Notes |
|---|---|---|---|---|---|
| **SAP S/4HANA Cloud** | Enterprise | Per-user/month, public vs. private edition | ~$150-400/user/mo list; enterprise deals often 50%+ off list | **Joule** — base tier free (action-allowance limited), Premium metered in "AI Units" (~€7/unit); custom agent dev via Joule Studio $42K-$96K/yr | 3-yr TCO $150K-$600K mid-market; full implementations $1.5M-$4M mid-size, $3M-$20M+ enterprise. SI fees = 40-60% of project cost. Consultant day rate $1,800-$2,500. |
| **SAP Business One** | Small business | Per-user/year | Professional $1,800-2,600/user/yr; Limited $650-1,100/user/yr | Joule (lighter) | Entry point for SAP into SMB; still consultant-dependent for setup |
| **SAP Business ByDesign** | Mid-market | Per-user/year | ~$1,700/user/yr + $100-124K implementation | Joule | Sits between Business One and S/4HANA |
| **Oracle NetSuite** | Growth/mid-market ($10M-$1B revenue) | Base platform fee + per-user + per-module add-ons | Base $999-5,000/mo; full user $129-199/user/mo; modules (OneWorld, Advanced Mfg, SuiteCommerce) $499-5,000/mo each | Fusion AI Agent Studio (100-600+ prebuilt agents); N/llm scripting; 2026 "Custom Tool Script Type" gives agents write-access via typed tool calls | ~40-41K customers; 6-10 modules typical mid-market deployment; SuiteSuccess = pre-configured industry templates; implementation 4-6 months typical |
| **Microsoft Dynamics 365 Business Central** | SMB/mid-market | Per named user/month | Essentials $80/user/mo, Premium $110/user/mo (Nov 2025 prices), Team Member $8/user/mo | Copilot — base free, advanced metered via "Copilot Credits" | 50-55K+ customers, passed NetSuite in customer count in 2025; implementation $25K-150K+ |
| **Odoo** | SMB, cost-sensitive | Flat per-user/month, ALL apps included (no per-module fee) | Standard $24.90/user/mo; Custom (self-host option) $37.40/user/mo; One App Free tier | Native AI (Lead Scoring, OCR, AI Fields) — Enterprise only; ecosystem mostly 3rd-party marketplace add-ons | 170K+ customers, ~$712M 2025 revenue, ~15% of global SMB ERP market (directional). Community edition is free/open-source but no SLA — real DevOps burden. Biggest differentiator: no per-module upcharge, unlike NetSuite. |

**Common complaints about SAP/legacy ERP (recurring across every source):** cost opacity and heavy negotiation gaps; consultant/SI dependency eating 40-60% of budgets; multi-year implementation cycles even for "modern" cloud editions; steep UX/training burden (memorized transaction codes); hidden cost of staying on legacy (slow close, blocked digital transformation); and — the exact wedge every AI-native challenger uses — **"AI bolted onto old data models, not built in."**

### 3.2 The AI-Native ERP Challenger Wave (2023-2026)

This is a genuinely new, fast-moving, well-capitalized category. It validates the thesis, but it's also direct competition if we go after English-speaking markets.

| Company | Latest round | Total raised | Bet |
|---|---|---|---|
| **Rillet** | $70M Series B (a16z + ICONIQ, mid-2025), following $25M Series A (Sequoia) | ~$95M+ | AI-native GL built by ex-N26 US CEO; 4-week implementations vs ~12mo legacy; continuous/daily close; customers incl. Bitwarden, Windsurf, Postscript |
| **DualEntry** | $90M Series A (Lightspeed, Khosla, GV, Contrary), Oct 2025 | ~$100M+ in 15mo, $415M valuation | Full financial suite rip-and-replace for NetSuite/SAP/Dynamics; targets the "$10M-$100M revenue gap"; claims $100B in journal entries processed with AI |
| **Campfire** | $65M Series B (Accel/Ribbit), Oct 2025, after $35M Series A months earlier | $100M in 12 weeks combined | Proprietary "Large Accounting Model" trained only on accounting data; explicitly wins customers away from NetSuite |
| **Light** (Copenhagen) | $30M Series A (Balderton), Sept 2025 | ~$43M | Rebuilt GL for speed (280M records <1s); multi-entity/multi-country hypergrowth targeting |
| **Everest** | $140M seed-stage (Sutter Hill), late 2024 | $140M | Founded by ex-SAP HANA architect Franz Färber — a serious technical bet built specifically against SAP |
| **Numeric** | $51M Series B (IVP), Nov 2025 | — | Different bet: close-automation layered **on top of** existing ERPs, not a replacement; ships an MCP server for agent access |
| **Nectari** | Launched Jan 2026 | — | AI copilot layered onto Sage/Acumatica — same "copilot on incumbent" bet as Numeric |
| **Puzzle** | ~$50M raised | — | AI-native ledger for startup/QuickBooks-tier market |

**Key strategic fork visible in this category:** rip-and-replace AI-native ERP (Rillet, DualEntry, Light, Everest) vs. AI-copilot-on-top-of-incumbent (Numeric, Nectari). **[DECISION NEEDED]** We should decide early which bet we're making — see §6 and §9.

**Important gap:** none of these are finance-only(mostly GL/AP/AR/close) — none cover manufacturing, full inventory/warehouse, HR/payroll, or CRM as broad operational ERP. None target Turkey or any e-Devlet-style compliance regime. This is real whitespace for a broader-scope, Turkey-first entrant.

### 3.3 Turkey Deep Dive

**Logo Yazılım — the incumbent to beat**

- Publicly traded (Borsa Istanbul: LOGO). FY2025 revenue **TRY 5.8B** (+9% real growth), net profit **TRY 1.5B**, cloud-based revenue **TRY 3.19B** (majority of business now), 11,200 new customers added in 2025.
- Market leader in Turkey's Enterprise Application Software space by customer count, cited at **85,000+ customers**. Became dominant in ERP specifically by acquiring **Netsis** (the #2 vendor) in 2013.
- Product lines: **Logo GO** (entry/micro), **Logo Tiger** (core mid-market ERP), **Logo j-Platform** (modern web-architecture ERP for mid/large + dealer networks), **Logo Netsis** (retained as separate brand post-acquisition), **Masraff** (AI-assisted expense management, 300+ businesses/50K+ users — their clearest AI feature, but adjacent, not core-embedded).
- Pricing: per-user/per-package license + mandatory annual **LEM** (license maintenance fee, first year usually bundled free) + separately-billed, reseller-quoted implementation/customization. **No public standardized price list** — this opacity is itself a market characteristic we can contrast against.
- **Documented, repeated criticisms** (Şikayetvar complaint site, LinkedIn reviews, 2025): support/call-center unavailability during invoicing outages; cloud ERP reliability bugs; ~2 years of unresolved WMS/stock-count issues for some users; "every update breaks something," notably worse after mandatory e-İrsaliye rollout; high LEM fees "without value in return"; heavy web client (cited ~5GB footprint).
- **Why companies still choose it anyway:** most complete/reliable GİB e-transformation compliance coverage reduces switching risk; large certified-reseller/"İş Ortağı" ecosystem; incumbent talent-pool familiarity (every accountant already knows it); Netsis acquisition removed the #2 independent competitor.

**Other Turkish vendors**

| Vendor | Ownership | Segment | Notes |
|---|---|---|---|
| **Netsis** | Acquired by Logo (2013) | Mid-size, manufacturing-leaning | Sold as "Logo Netsis," not independent |
| **Mikro Yazılım** | 100% owned by Italian **TeamSystem** (2023) | SMB accounting-first (Run/Jump/Fly tiers) | Strong with mali müşavir (accountant) community |
| **Zirve Yazılım** | Same group as Mikro (DST Teknoloji / MikroGrup) | Budget SMB | Grouped with "economical" tier alongside Akınsoft, DIA, Vega, Luca |
| **Paraşüt** | Same group as Mikro | Micro/freelancer/e-ticaret cloud accounting | ~TRY 110+KDV/mo entry tier; simple, cloud-first UX |
| **Nebim (V3/ERA)** | Independent | Retail/wholesale/franchise verticals | Tight ERP+POS+inventory integration for retail workflows |
| **Uyumsoft (Liox ERP)** | Independent | Mid-market, sector-specific | Most vocal Turkish vendor on generative-AI-in-ERP messaging (thought-leadership stage, not proven depth) |
| **Barsoft** | Independent, regional | Retail/restaurant/gas station niche | Small, regional |

No AI-native ERP or back-office startup was identified as currently active in Turkey specifically — a genuine, if unverified, white-space signal (worth re-checking against Turkish-language startup press like Webrazzi before betting the whole strategy on it).

### 3.4 Turkish Compliance — the Existential Requirement

This is the single most important localization dependency and the primary reason foreign SaaS ERPs don't casually enter Turkey. **[RESEARCH GAP: exact thresholds shift via GİB Tebliğ roughly annually — re-verify against the live communiqué before finalizing engineering scope.]**

- **e-Fatura (e-Invoice):** mandatory above TRY 3M prior-year gross revenue (lower thresholds for e-commerce/real estate at TRY 500K; hotels have no threshold at all — mandatory regardless of size). Penalty for non-compliance: 10% special irregularity fine (VUK).
- **e-Arşiv Fatura:** backstop for anyone below the e-Fatura threshold, for B2C/non-registered counterparties above small transaction limits (~TRY 3,000/transaction cited for simplified-basis taxpayers).
- **e-Defter (e-Ledger):** mandatory for anyone on e-Fatura keeping accrual-basis books.
- **e-İrsaliye (e-Waybill):** mandatory for e-Fatura filers with 2025 revenue ≥ TRY 10M.
- **e-Müstahsil Makbuzu:** role-based (buyers from tax-exempt farmers, Hal Kayıt Sistemi members) — not revenue-based; GİB can also force any taxpayer onto it via risk-scoring, independent of turnover.
- **SGK / e-Bildirge:** mandatory monthly payroll/social-security submission for anyone with employees — table stakes for any payroll module.
- **KDV (VAT) / e-Beyanname:** as of Sept 2025, accountants in pilot provinces can submit client VAT returns directly from their own software via GİB web-service integration, rolling out province by province — signals GİB is pushing toward direct software-to-government API integration as the default expectation, not an option.

**Implication for engineering scope:** this requires a **dedicated, continuously-maintained compliance/localization team** tracking GİB Tebliğ changes as an ongoing cost center — not a one-time integration project. This is likely the largest real moat protecting Logo today, and the largest real cost we need to budget for turning it into our moat instead.

### 3.5 Turkish Market Sizing & Price Sensitivity

- **3,936,542 SMEs** in Turkey (TÜİK 2024) = 99.6% of all enterprises; SMEs = 68.5% of employment, 44.1% of turnover.
- **ERP penetration is low and scales sharply with firm size:** only **23.6%** of 10-49 employee firms use ERP at all vs. **46.0%** of 50-249 employee firms (TÜİK 2025). CRM penetration is even lower (9.9% / 18.4%). **This means 76%+ of small firms have no real ERP today** — a large greenfield opportunity rather than a pure displacement fight.
- **Price sensitivity is real and structural:** Turkish SMEs spend on average **<0.5% of revenue** on enterprise application software (PwC Strategy&, 2021) — a rounding-error-cost market historically, not a strategic-value-cost market.
- **Countervailing signal:** cloud infrastructure and AI-based services are reportedly starting to capture a larger share of spend — willingness to pay rises when the pitch shifts from "digitized paperwork" to "automation that visibly replaces headcount or catches costly errors." This is the framing we should lead with, not "cheaper than Logo."
- **KOSGEB KOBİ Dijital Dönüşüm Destek Programı**: interest-free/subsidized credit, TRY 1M-20M, 36-month repayment — but **restricted to NACE-classified manufacturing businesses with positive operating profit**, requiring a prior Digital Transformation Assessment Report. Not a general software-adoption subsidy — relevant mainly for our manufacturing-vertical customers, and a real go-to-market lever specifically there.

### 3.6 Competitive Positioning Summary

| Axis | SAP | Logo & Turkish incumbents | AI-native challengers (Rillet, DualEntry...) | **Us** |
|---|---|---|---|---|
| Price transparency | Opaque, negotiated | Opaque, reseller-quoted | Mostly transparent SaaS pricing | Transparent, public tiers |
| AI depth | Retrofitted (Joule), improving fast | Adjacent app only (Masraff), not core-embedded | AI-native core, but finance-scope only | AI-native core, full operational scope |
| Turkish compliance | Present via local partners, not core strength | Deep, mature, but buggy/unreliable | None | Deep, core, reliable — the moat we build deliberately |
| Implementation speed | Months to years | Weeks to months (SMB tier) | Days to weeks (finance-only scope) | Weeks (target), AI-accelerated setup |
| Modularity | Module-based, expensive add-ons | Package-based, opaque pricing | Mostly single-product (GL/close) | Core + independently-priced packages |
| Target scope today | Enterprise | SMB→mid-market | Finance/accounting only | Full ERP: finance + ops + HR + mfg + retail |

---

## 4. Should AI Be a Package or Embedded by Default?

**[DECISION — recommended default, confirm or override]**

**Base AI (the chat panel, natural-language Q&A, cross-module explanations) is embedded by default in every tier, not sold as an add-on.** This is the core product thesis — if AI is optional, we're just another ERP with a chatbot upsell, which is exactly the "bolted on" positioning we're attacking. Every incumbent studied (SAP, Microsoft, Oracle) reached the same conclusion: base copilot ships free/included, and only the *deep end* is metered.

What **is** tiered/metered, mirroring the industry-wide pattern (SAP's Action Allowances + Joule Premium AI Units, Microsoft's Copilot Credits, Oracle's OCI consumption charges for custom agents):

- **Included in every tier:** conversational Q&A across owned modules/packages, explanations of any record/workflow, guided report generation, basic anomaly flags.
- **Metered / higher-tier gated ("AI Actions" or credits):** agentic multi-step automation (e.g., auto-drafting a full purchase order from an email, running a multi-step reconciliation sweep, autonomous forecasting agents), high-volume usage, and custom agent/workflow building (a "Joule Studio"-equivalent for us).
- **Enterprise-only:** custom agent development tooling, dedicated fine-tuned/embedded semantic layer per customer, on-prem/VPC-isolated model deployment for regulated customers.

This gives us: (1) a defensible "AI-native, not AI-added" marketing claim, (2) a pricing lever that scales with actual value delivered (heavy automation users pay more) rather than penalizing light users, and (3) protection against the cost blowout SAP/Microsoft both hit before they introduced metering. See §7 for how this folds into pricing tiers.

---

## 5. AI Architecture Principles

(Full detail belongs in an engineering design doc; this section captures the decisions that shape product scope and packaging, based on architecture patterns converged upon by SAP Knowledge Graph, Microsoft Dataverse Semantic Index, and the open-source semantic-layer ecosystem — dbt MetricFlow, Cube.dev, Wren AI.)

1. **A semantic/metrics layer sits between the LLM and the database — the LLM never free-composes SQL over raw tables.** Enterprise-realistic benchmarks show raw text-to-SQL accuracy collapsing from ~91% (academic benchmark) to ~21% (enterprise schema) — 81% of errors are schema/semantic misunderstanding, not syntax. A governed semantic layer (pre-modeled metrics, dimensions, joins, business logic) lifts this back to 95-100% in cited benchmarks. **This is treated as a mandatory architecture constraint, not an optimization** — e.g., "gross margin" must always be computed by the same deterministic, versioned definition, never re-derived ad hoc by the LLM (the "metric drift" failure mode).
2. **Read (Q&A) and write (actions) are architecturally separate trust domains.** Questions route through the deterministic semantic layer with the LLM only narrating results. Actions (create PO, post journal entry, approve invoice) are explicit, schema-typed tools with embedded business-rule validation — the MCP (Model Context Protocol) pattern, now a de facto industry standard, mirrored in NetSuite's 2026 "Custom Tool Script Type."
3. **Permission enforcement happens at the data-access layer the AI calls into — reusing the app's existing row/field-level security — never as a post-retrieval filter.** This is the single most-cited, highest-severity failure mode in the market: Microsoft 365 Copilot's disclosed EchoLeak (CVE-2025-32711) and SearchLeak (CVE-2026-42824) incidents both trace back to permission architecture gaps the AI made newly exploitable, not the model itself. Our AI layer must never have broader access than the requesting user already has through the normal UI.
4. **Human-in-the-loop confirmation for all mutating actions above a configurable risk/dollar threshold**, mirroring SAP's procurement Joule agent (auto-approve below threshold, flag above) and Oracle's Payables Agent (auto-processes, human review on edge cases). Implemented as a durable "pending_approval" checkpoint, not an ephemeral in-memory flag.
5. **Full AI audit trail by default:** prompt, retrieved context, tool calls, and human approvals/rejections logged as an append-only, tenant-scoped record — both for trust/debugging and because EU AI Act high-risk obligations reach full enforcement Aug 2, 2026 (fines up to €15M/3% global turnover) for AI touching employment/lending/critical-decision categories, which will matter once we ship HR/payroll AI features.
6. **Golden-query library with a feedback loop:** verified NL↔query pairs retrieved as few-shot grounding; user corrections to AI-generated queries/actions feed back into the library — a cheap, high-leverage accuracy mechanism every serious vendor uses.
7. **Latency mitigation is a first-class concern, not an afterthought:** semantic/result caching, pre-aggregation for expensive rollups, and parallel scatter-gather execution for multi-part analytical questions, rather than naive sequential computation over raw transactional tables.

---

## 6. Product Structure: Core + Packages

### 6.1 Core Platform (not sold separately — the mandatory foundation every customer runs)

- **General Ledger & Chart of Accounts** — multi-currency, multi-entity ready from day one (avoids the bolt-on multi-entity pain NetSuite/SAP customers report)
- **Basic AR/AP** — invoicing, payments, aging
- **User, Role, and Permission model** — the row/field-level security substrate the AI layer depends on (§5.3)
- **AI Chat Layer** — the right-panel assistant, embedded everywhere, always included (§4)
- **Localization/Compliance Engine** — pluggable per-country; Turkey Localization Pack (§6.3) is the first and most invested-in instance
- **Audit & Logging Infrastructure** — application audit log + AI action audit trail (§5.5)
- **Base Reporting/BI** — standard financial statements, dashboards
- **Data Migration & Onboarding Engine** — imports a new customer's existing data (chart of accounts, master data, historical transactions) from their prior system, via direct connectors to common Turkish incumbents (Logo, Netsis, Mikro) where feasible and via structured file/database export otherwise, with AI-assisted mapping and a validation/dry-run step before anything touches production data. Included for every tenant, not sold separately — it's the switching-cost killer, not a revenue line.

### 6.2 Independently-Priced Packages (snap into Core, share one data model + AI layer)

| Package | Core functionality | Primary competitors' equivalent |
|---|---|---|
| **Purchasing/Procurement** | Purchase orders, vendor management, approval workflows | SAP Ariba, NetSuite Procurement, Logo Tiger purchasing |
| **Inventory & Warehouse Management** | Stock, multi-warehouse, barcode/WMS | NetSuite WMS, Logo Netsis stock module |
| **Manufacturing/Production (MRP)** | BOM, work orders, capacity planning | SAP PP, NetSuite Advanced Manufacturing |
| **Sales & CRM** | Pipeline, quotes, order management | NetSuite CRM, Logo CRM |
| **HR & Payroll (Turkey-aware)** | Employee records, payroll, SGK/e-Bildirge integration | Logo İK, İK360, BordroPlus |
| **Project Management** | Time tracking, project costing, PSA | NetSuite PSA |
| **POS/Retail** | Point of sale, multi-store | Nebim V3/ERA |
| **E-commerce Integration** | Marketplace/storefront sync | Odoo e-commerce, Paraşüt e-ticaret |
| **Advanced BI/Analytics** | Custom dashboards, forecasting | SAP Analytics Cloud, NetSuite Analytics |
| **Advanced AI Agents Pack** | Agentic automation, autonomous forecasting/reconciliation agents, custom agent builder | SAP Joule Studio, Oracle Fusion Agent Studio |

### 6.3 Localization Packs (country-specific compliance — sold bundled by geography, not optional where legally required)

- **Turkey Localization Pack** (launch priority): e-Fatura, e-Arşiv, e-Defter, e-İrsaliye, e-Müstahsil Makbuzu, SGK/e-Bildirge, KDV/e-Beyanname integration, GİB API maintenance as an ongoing service commitment (not a one-time build).
- Future packs (Phase 3+): other markets, evaluated once Turkey + initial English-market traction is proven.

**[DECISION NEEDED — rip-and-replace vs. copilot-on-incumbent, per §3.2's strategic fork]:** given our full operational scope ambition (not finance-only), the natural answer is **rip-and-replace / full ERP**, differentiated from Rillet/DualEntry by *breadth* (manufacturing, inventory, HR, retail — not just GL/close) and from Logo/SAP by AI-native architecture + transparent pricing. A "copilot layered on top of Logo" product is a smaller, faster-to-market alternative worth scoping as a possible Phase 0 wedge (see §9) if full-ERP build time is a concern.

---

## 7. Pricing & Packaging Strategy

### 7.1 Tiering Philosophy

Public, transparent tiers (a direct contrast to Logo's reseller-quoted model and SAP's opaque enterprise negotiation). Every tier includes Core + embedded base AI; packages are added à la carte, similar to how NetSuite prices modules — but with Odoo's flat, non-punitive per-user philosophy applied within each package rather than NetSuite's steep $499-5,000/month per-module fees.

### 7.2 Illustrative Tiers (Turkey pricing shown in TRY; international in USD — figures are a starting proposal, not final)

| Tier | Target | Core price | Included packages | AI |
|---|---|---|---|---|
| **Starter** | 1-15 employees, first ERP ever | ~$15-25/user/mo (~TRY 500-800/user/mo) | Core only + 1 package of choice | Base AI chat included; no agentic actions |
| **Growth** | 15-75 employees | ~$35-50/user/mo | Core + up to 4 packages | Base AI included + limited monthly AI Action credits |
| **Professional** | 75-250 employees | ~$60-90/user/mo | Core + unlimited packages | Base AI + generous AI Action credits + advanced BI |
| **Enterprise** | 250+ employees, multi-entity | Custom quote | Everything + custom packages | Full agentic automation, custom agent builder, dedicated support, on-prem/VPC model option |

Each package beyond the included set: **flat per-user add-on** (e.g., +$5-15/user/mo), not NetSuite-style flat per-month-regardless-of-size fees — keeping cost proportional for small teams, which is exactly where Logo/SAP both fail SMBs today.

**AI Action credits** (metered layer per §4): bundled monthly allotment per tier, overage billed per-action or per-credit-pack, mirroring SAP's Action Allowance / Microsoft's Copilot Credits pattern — proven, don't reinvent.

### 7.3 Cost Comparison vs. Incumbents (illustrative, for positioning collateral)

| | SAP (mid-market) | Logo (SMB, est.) | **Us (Growth tier, ~20 users)** |
|---|---|---|---|
| Year-1 all-in cost | $150K-$600K+ | TRY 60K-150K license + undisclosed implementation | ~$8,400-12,000/yr (~TRY 3M-4.3M) transparent, no separate reseller quote needed |
| Implementation time | 6mo-2yr+ | Weeks-months (reseller dependent) | Weeks, AI-accelerated setup (target) |
| Ongoing AI cost | Metered, can spike | None (bolt-on Masraff only) | Included base tier, predictable metered overage |

**[RESEARCH GAP]** — real Turkish implementation labor costs (as distinct from license cost) were not found publicly; worth a direct call to 2-3 Turkish ERP consulting firms before publishing external-facing pricing comparisons.

### 7.4 Turkish Market Pricing Sensitivity Adjustment

Given the <0.5%-of-revenue historical spend ceiling (§3.5), Starter tier pricing for Turkey should be positioned and marketed around **automation ROI** (hours saved, errors caught) rather than feature lists — the same reframe that's reportedly already shifting AI/cloud spend upward in this market. Consider a manufacturing-vertical bundle co-marketed with KOSGEB digital-transformation-credit eligibility as a Turkey-specific go-to-market lever (§3.5).

---

## 8. Go-to-Market Strategy

1. **Turkey-first, small-end-first.** Target the 76%+ of 10-49 employee firms with no ERP today, not a head-on fight for Logo's existing enterprise accounts. Lower switching-cost anxiety, lower CAC, and validates the compliance engine on real GİB traffic before it needs to handle enterprise-scale volume.
2. **Compliance credibility as the entry ticket, AI as the differentiator.** Nobody adopts an ERP in Turkey that can't do e-Fatura/e-Defter/e-İrsaliye reliably — this is table stakes, not a selling point on its own. Once that trust bar is cleared, AI-native UX and pricing transparency become the actual differentiators against Logo.
3. **Build (or partner into) a reseller/consultant channel deliberately, but keep it thinner than Logo's.** Logo's İş Ortağı network is both a strength (distribution, familiarity) and a cost center customers resent (opaque implementation billing). A leaner certified-partner program, plus AI-accelerated self-serve onboarding for the Starter tier, can undercut this.
4. **Secondary: English-speaking SMB/mid-market**, competing in the same category as Rillet/DualEntry but differentiated by full operational scope (manufacturing/inventory/HR, not finance-only) — likely a Phase 3+ effort once Turkey traction and the compliance-engine architecture (proof that we can do deep, hard localization well) are proven.
5. **Vertical wedge candidates worth testing:** manufacturing SMEs (KOSGEB credit eligibility as a real acquisition lever) and retail/multi-store (competing with Nebim's POS+inventory tightness) both look like defensible first verticals.
6. **Make switching effortless — migration tooling as a sales weapon, not just a support function.** The #1 objection a Logo/Netsis/Mikro customer will raise is "what happens to my historical data and my compliance continuity if I switch?" A working, demoable migration path (import their real chart of accounts and a slice of real history in a live sales conversation) turns that objection into a differentiator. This should be a named capability in sales collateral, not a quiet backend feature.

---

## 9. Roadmap (Phased)

**[DECISION NEEDED — this is a proposal, needs your sign-off on sequencing]**

- **Phase 0 (validate):** Decide rip-and-replace-full-ERP vs. copilot-on-incumbent-Logo as the wedge (§3.2, §6.3). If speed-to-revenue matters most, a "smart AI layer that sits on top of an existing Logo/Netsis install" could be a faster initial product than a full Core rebuild — worth a explicit go/no-go conversation.
- **Phase 1 (MVP):** Core platform (GL, AR/AP, users/permissions, base AI chat layer, audit infra) + Turkey Localization Pack (e-Fatura/e-Arşiv/e-Defter minimum) + 1-2 packages (likely Purchasing + Inventory, the most universally needed). Target: Starter + Growth tiers only.
- **Phase 2:** Add Manufacturing, HR/Payroll (SGK integration), CRM/Sales packages. Introduce metered AI Action credits and Professional tier. Expand e-İrsaliye/e-Müstahsil/full e-Beyanname compliance depth.
- **Phase 3:** POS/Retail, E-commerce integration, Advanced BI, Advanced AI Agents Pack (custom agent builder). Evaluate first non-Turkey market entry.
- **Phase 4:** Enterprise tier (multi-entity, on-prem/VPC AI option), additional country localization packs.

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| GİB compliance requirements shift ~annually — underestimating this is the #1 way to lose Turkish customer trust | Dedicated, permanent compliance/localization team from day one, not a one-time project; budget it as ongoing headcount, not a feature |
| AI hallucination on financial numbers destroys trust instantly in an accounting context | Mandatory semantic-layer architecture (§5.1) — LLM never free-composes financial SQL; deterministic computation + LLM narration only |
| Permission/data-leakage failures (per EchoLeak/SearchLeak precedent) | AI layer must call through the same RLS-aware access layer as the UI; no separate broader-access AI service account (§5.3) |
| Turkish market's <0.5%-of-revenue software spend ceiling limits achievable ARPU | Lead marketing with automation-ROI framing, not feature/price comparison; use vertical bundles (manufacturing + KOSGEB) to justify higher willingness-to-pay |
| Well-funded AI-native competitors (DualEntry, Rillet, Everest) could expand into broader ERP scope or into Turkey | Move faster on compliance-engine depth (real moat, hard to replicate quickly) and full operational scope (they're finance-only today) |
| Full-ERP build is a multi-year effort before reaching revenue-relevant scope | Consider Phase 0 wedge decision seriously — narrower first product (e.g., AI layer + Turkey compliance + 1-2 packages) de-risks time-to-revenue |
| Legacy data (Logo/Netsis/Mikro exports) is inconsistent across product versions, customizations, and years of manual workarounds — migration could become a bottomless services pit instead of a repeatable product feature | Scope migration connectors around a defined, versioned set of source-system schemas; treat anything outside that set as a manual-import fallback (spreadsheet templates), not an open-ended commitment to support every legacy customization |

---

## 11. Open Questions for You

1. Rip-and-replace full ERP vs. AI-copilot-layered-on-existing-Logo/Netsis-installs as the initial wedge — which risk profile do you want (§3.2, §9 Phase 0)?
2. Which package should ship first after Core: Purchasing, Inventory, or something else based on customer conversations you may already be having?
3. Do we want a services/implementation arm ourselves (revenue + control over onboarding experience) or stay pure-SaaS and rely on partners (lower overhead, less quality control) — this affects both margin structure and the "fast implementation" differentiator.
4. Target company name/brand — this doc has been written vendor-name-agnostic; worth deciding early since it affects domain, trademark search, and Turkish-market brand testing.
5. Any existing customer conversations, LOIs, or design partners already in motion that should reshape the Phase 1 package priorities above?
6. How "magic" should migration be on day one — do we invest in direct read connectors against on-prem Logo/Netsis/Mikro databases (higher engineering cost, stronger demo/sales impact), or launch with structured file/export-based import only and add direct connectors once we have real customer databases to build against (see `technical.md` §9)?

---

## Appendix: Key Sources Consulted

Global ERP pricing/TCO: Redress Compliance, Top10ERP, erpimplementationcost.com, SAP News Center, aimultiple, ERP Research, Hyperbots, MSDynamicsWorld, OEC.sh, Getlatka, GloriumTech.

AI-native ERP startups: TechFundingNews, PR Newswire, Balderton Capital, Kruze Consulting, Yahoo Finance, New Market Pitch.

Turkish market: Logo IR filings (cdn.logo.com.tr), Fintechtime, Paraanaliz, Tracxn, Şikayetvar, TÜİK 2024/2025 releases, KOSGEB program documentation, Sovos TR, tokeninc.com, mavvo.com.tr, eticaretradari, Patronlar Dünyası, FinTech İstanbul.

AI architecture: SAP Architecture Center, SAP Knowledge Graph docs, Microsoft Power Platform Blog, Oracle news/Fusion Agent Studio announcements, epiqinfo.com, dbt/getdbt.com semantic layer benchmarks, Wren AI, Cerbos, Couchbase, arXiv enterprise text-to-SQL benchmark (2604.25149).

*(Full URL list available on request — trimmed here for readability; research was conducted via three parallel research passes in July 2026.)*
