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

## 4. AI Chat Layer v1: needs an LLM API key to actually talk (not a blocker on building it)

**What's built:** the read-only Q&A path (`REQ-CORE-AI-001/002/003/004/005/006/008/009`) — `apps/ai_core` (semantic-layer registry + tool-calling loop over Claude + audit logging) plus a `metrics.py`-equivalent (`ai_tools.py`) in every package (Core, Inventory, Purchasing, Sales & CRM, Manufacturing, HR & Payroll) registering read-only questions the assistant can answer with a real, cited figure — cash position, AR/AP aging, stock on hand, open POs/SOs/leads, pending work orders, latest payroll cost. The frontend AI side-panel (already scaffolded from Phase 0) is now wired to it end-to-end.

**What's needed from you:** an Anthropic API key, set as `ANTHROPIC_API_KEY` in `backend/.env`. Without it, the assistant runs in a deliberate "not configured" state — it says so plainly rather than crashing or fabricating an answer (`REQ-CORE-AI-009`) — so this isn't blocking anything else, just inactive until the key is supplied. `AI_LLM_MODEL` (defaults to `claude-sonnet-5`) is also configurable in `.env` if you want to point it at a different model/tier later.

**One caveat worth knowing:** there's no Anthropic API key available in this dev environment, so the tool-calling loop (`apps/ai_core/chat.py` + `llm_gateway.py`) is verified by tests with the LLM call mocked out (control flow, permission gating, audit logging, graceful degradation) but has not yet been smoke-tested against the real Anthropic API end-to-end. The multi-turn tool-result wire format follows the SDK's documented shape, but the first real conversation once a key is added is worth watching for any request-shape mismatch before trusting it broadly.

**What's deliberately deferred, not forgotten** (each is a real chunk of `technical.md` §8 on its own):
- **The write/action path** (`REQ-CORE-AI-007/010`, §8.4): the AI can't create a PO, post a journal entry, etc. yet. The `PendingApproval` state-machine model and per-tenant approval-threshold config described in the architecture doc don't exist yet — this pass is Q&A only. The frontend's `pendingAction` UI treatment is still there (built in Phase 0) so this is a backend addition later, not a UI rewrite.
- **Metered AI Action credits / billing** (`REQ-CORE-AI-011`, §8.8, Phase 2 scope in `development-plan.md`) — the gateway module is structured so every call already passes through one place, but no usage ledger or billing reconciliation exists yet.
- **RAG over uploaded documents** (§8.7) — contract/policy Q&A isn't wired; today's assistant only answers questions the registered metrics can compute.
- **Golden-query regression eval** (§8.9) — no automated accuracy-regression suite yet; today's test coverage is unit/integration correctness of each metric and the tool-calling loop's control flow, not answer-quality evaluation against real English/Turkish phrasing variety.
- **Conversation persistence** — each chat turn is stateless server-side beyond the audit log; the frontend resends prior turns as context. A durable conversation history model is a small addition later if it's wanted (e.g. for a "recent conversations" list), not a redesign.

## What's proceeding despite these blockers

Per your instruction, Phase 1 continues into **Phase 2 scope** (`development-plan.md` §5) where it doesn't depend on either decision above — Sales & CRM, Manufacturing, and HR & Payroll have shipped (mirroring the Purchasing pattern already in Phase 1: order → fulfillment/receipt → stock movement → auto-generated AR/AP document), and now the AI Chat Layer v1 described above. Remaining Phase 2 items — multi-entity consolidation and the metered AI agentic layer — are next; SGK e-Bildirge and the Mikro connector remain blocked on decisions #1/#2 above the same way e-Fatura and the Logo connector were in Phase 1.
