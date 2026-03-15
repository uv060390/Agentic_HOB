# PLAN.md — BrandOS Build Plan

---

## Vision

BrandOS is a zero-employee D2C operating system where every brand in a portfolio is run by a team of AI agents — each with defined roles, budgets, tools, and reporting lines — orchestrated server-side and controlled by a single human founder through WhatsApp and Telegram. The system replaces dashboards with conversations, replaces headcount with agents, and replaces manual operations with autonomous heartbeats. It is built for Indian D2C brands, optimised for cost (model routing, Cerebras for non-reasoning tasks, Hetzner infrastructure), and hardened against the security and reliability gaps in existing AI-company frameworks.

---

## Current Status

**Week 0 — Not Started**

No code has been written. Architecture is finalised. CLAUDE.md and PLAN.md are the first deliverables.

---

## Build Sequence

### Week 1 — Foundation

Goal: Gateway running, database schema live, model router working, secrets flowing from Infisical.

- [ ] Initialise monorepo: `pyproject.toml`, `docker-compose.yml`, `Dockerfile`, `.gitignore`
- [ ] Set up `docker-compose.yml` with PostgreSQL 15 and Infisical containers
- [ ] Create SQLAlchemy models: `company`, `agent_config`, `audit_entry`, `token_usage`, `ticket`, `tool_registry`, `tool_config`, `specialist_hire`
- [ ] Write and run Alembic migrations for all initial tables
- [ ] Build `src/shared/config.py` — Pydantic Settings loading from env vars
- [ ] Build `src/shared/db.py` — SQLAlchemy async engine and session factory
- [ ] Build `src/vault/client.py` — Infisical SDK wrapper with per-brand, per-agent scoping
- [ ] Build `src/vault/sandbox.py` — mock credential provider for local dev
- [ ] Build `src/llm/provider.py` — unified LLM interface (`call(task_type, messages)`)
- [ ] Build `src/llm/anthropic.py` — Anthropic API client (Opus + Sonnet)
- [ ] Build `src/llm/cerebras.py` — Cerebras API client (Llama 3.3 70B + 3.1 8B)
- [ ] Build `src/core/model_router.py` — task type → model/provider mapping
- [ ] Build `src/core/budget_enforcer.py` — token tracking, per-agent monthly hard limits
- [ ] Build `src/core/audit_log.py` — append-only audit entry writer
- [ ] Build `src/gateway/app.py` — FastAPI skeleton with health check endpoint
- [ ] Build `src/gateway/auth.py` — API key validation middleware
- [ ] Build `src/gateway/sanitizer.py` — prompt injection sanitizer (strip instructions, XML tags, role-play attempts from external data)
- [ ] Write `scripts/seed_companies.py` — seed AIM (active) + LembasMax (wind-down)
- [ ] Write unit tests: `test_model_router.py`, `test_budget_enforcer.py`, `test_sanitizer.py`
- [ ] Verify end-to-end: Gateway receives request → auth passes → sanitizer runs → model router returns correct model → audit log written → budget tracked

### Week 2 — Agents, Org Chart, and Specialist Hiring System

Goal: Base agent framework running. AIM CEO and Finance agents executing real tasks. Specialist hiring pipeline designed. AGENTS.md written.

- [ ] Build `src/agents/base_agent.py` — abstract base class: `run(task)`, `report()`, `get_tools()`
- [ ] Build `src/core/company_registry.py` — CRUD for companies, isolation enforcement
- [ ] Build `src/core/org_chart.py` — agent hierarchy per brand, reporting lines, standing vs specialist distinction
- [ ] Build `src/core/goal_ancestry.py` — task → project → company → mission tracing
- [ ] Build `src/core/ticket_system.py` — create, update, thread, close tickets
- [ ] Build `src/agents/templates/ceo.py` — CEO agent: weekly synthesis, goal alignment
- [ ] Build `src/agents/templates/finance.py` — Finance agent: unit economics, P&L draft
- [ ] Build `src/agents/registry.py` — instantiate agent templates per brand from DB config (standing + specialist)
- [ ] Build `src/agents/hiring_manager.py` — diagnose brand KPIs → propose specialist hires → route to governance for approval
- [ ] Build `src/agents/specialists/data_scientist.py` — ML model building, CAC optimisation, LTV prediction
- [ ] Build `src/agents/specialists/engineer.py` — ad tech pipelines, data infra, automation
- [ ] Build `src/agents/specialists/data_analyst.py` — deep-dive analysis, cohort breakdowns, funnel diagnostics
- [ ] Build `src/core/governance.py` — approve, override, pause, rollback controls (including specialist hire approval)
- [ ] Seed agent configs for AIM brand (CEO + Finance as standing agents with model tiers and budgets)
- [ ] Write integration test: CEO agent receives a task, calls LLM through provider, writes audit entry, creates ticket, reports result
- [ ] Write integration test: Finance agent calculates unit economics from Supabase data, writes audit entry
- [ ] Write integration test: hiring manager detects KPI anomaly → proposes specialist → governance approval → specialist instantiated → specialist runs → specialist wound down
- [ ] Write `AGENTS.md` — full per-agent definitions (role, tools, model tier, budget cap, heartbeat schedule, brand assignments) with separate section for specialist agent catalogue
- [ ] Verify brand isolation: LembasMax agent cannot access AIM data or credentials

### Week 2.5 — Multi-Agent Orchestration, Creative Library, and Optimizer

Goal: Agents can hand off tasks to each other through a structured workflow engine. Creative outputs are persisted to a Google Drive Creative Library with CTR feedback. Optimizer specialist closes the quality loop.

Jira tickets: AM-98 through AM-106.

- [x] **AM-98** — Build `src/core/orchestrator.py` — `Workflow`, `WorkflowStep`, `WorkflowRun` dataclasses; `run_workflow()` sequential executor; `WORKFLOW_REGISTRY` with `creative_optimisation` (4 steps) and `competitor_intelligence` (3 steps)
- [x] **AM-99** — Add `delegate()` method to `src/agents/base_agent.py` — allows agents to hand off sub-tasks to other agent templates within the same brand; deferred import to avoid circular dependency
- [x] **AM-100** — Build `src/agents/specialists/optimizer.py` — `OptimizerAgent` with 4 task subtypes: `set_objective`, `trigger_workflow`, `evaluate_quality` (LLM YES/NO judge), `iterate_or_complete`
- [x] **AM-101** — Build `src/tools/storage/google_drive.py` + `__init__.py` — Creative Library: `save_creative()`, `get_top_creatives()`, `update_actual_ctr()`; Google Drive file storage + `creative_library` metadata table; stubbed for Week 2.5, full implementation in Week 3
- [x] **AM-102** — Write Alembic migration `003_orchestration_tables.py` — creates `workflow_run`, `workflow_step`, `creative_library` tables; full `downgrade()` included
- [x] **AM-103** — Add `WorkflowError` and `CreativeLibraryError` to `src/shared/exceptions.py`
- [x] **AM-104** — Add `WorkflowStepResult`, `WorkflowRunResult`, `CreativeLibraryEntry` Pydantic models to `src/shared/schemas.py`
- [x] **AM-105** — Write `scripts/seed_apify_tool_config.py` — idempotent seeder for Apify Facebook Ads Library custom adapter config for AIM brand (`tool_slug: apify_fb_ads`)
- [x] **AM-106** — Write `tests/integration/test_workflow_orchestration.py` — 14 async tests covering workflow registry, step chaining, failure propagation, delegate brand isolation, Creative Library, and OptimizerAgent lifecycle

### Week 2.7 — Onboarding Wizard

Goal: A new founder can message the bot on WhatsApp or Telegram and be walked through full BrandOS setup in a single conversation — brand basics, LLM keys, messaging, tools, budget caps, and auto-provisioning. No manual VPS access required.

Jira tickets: AM-107 through AM-113.

- [x] **AM-107** — Build `src/core/onboarding.py` — persistent, resumable onboarding state machine backed by `onboarding_session` table. `OnboardingStep` dataclasses, 30+ step definitions, `process_input()` core step engine, all validators (with live API test calls), auto-actions (`auto_register_telegram_webhook`, `auto_register_whatsapp_webhook`, `run_auto_provision`), dynamic tool credential queue, prompt formatter
- [x] **AM-108** — Build `src/gateway/routes/onboarding.py` — FastAPI route handler: `POST /api/v1/onboarding/message`, `GET /api/v1/onboarding/status/{founder_id}`, `POST /api/v1/onboarding/reset/{founder_id}`. DB helpers for session get/create/update (raw SQL). `format_for_channel()` (WhatsApp vs Telegram), `_progress_line()`, `is_onboarding_complete()` / `needs_onboarding()` for intent router integration. Registered in `app.py`.
- [x] **AM-109** — Write `tests/unit/test_onboarding.py` — 35+ async tests: step registry, tool queue, progress counting, config application, validators, process_input step machine, secret routing (Vault not DB), auto-step execution, injection detection, optional step skip, format helpers, next-step routing, `needs_onboarding()` DB helper
- [x] **AM-110** — Write Alembic migration `004_onboarding.py` — creates `onboarding_session` table with `founder_id`, `channel`, `status`, `current_step_id`, `completed_steps` (JSON), `collected_config` (JSON), `pending_tool_steps` (JSON), `company_id`, `error_message`, `last_message_at`; indexes on `founder_id`, `status`, `channel`
- [x] **AM-111** — Add `OnboardingError` and `StepValidationError` to `src/shared/exceptions.py`
- [x] **AM-112** — Add `set_brand_secret()` and `set_shared_secret()` to `src/vault/client.py` — write-only path used exclusively by onboarding; read-only in all other contexts
- [ ] **AM-113** — Wire `needs_onboarding()` into `src/gateway/intent_router.py` — check before every incoming message dispatch; route to `handle_onboarding_message()` instead of agent layer if onboarding is incomplete

### Week 3 — Heartbeats, Tool Layer, and Remaining Agents

Goal: Agents running on schedules without human trigger. Full tool layer with custom adapter live. SKILLS.md written.

- [ ] Build `src/core/heartbeat.py` — APScheduler integration, cron-style schedule per agent
- [ ] Build `src/agents/templates/scout.py` — Scout agent: Meta Ad Library scraping, Reddit monitoring
- [ ] Build `src/agents/templates/cmo.py` — CMO agent: campaign briefs, creative direction
- [ ] Build `src/agents/templates/creative.py` — Creative agent: ad copy, hooks, variants
- [ ] Build `src/agents/templates/performance.py` — Performance agent: Meta Ads API, bid management
- [ ] Build `src/agents/templates/ops.py` — Ops agent: supplier follow-ups, 3PL coordination, FSSAI calendar
- [ ] Build `src/agents/holdco/portfolio_cfo.py` — cross-brand consolidated P&L
- [ ] Build `src/agents/holdco/bd_agent.py` — new brand scouting
- [ ] Build `src/agents/specialists/seo_aeo.py` — SEO + AEO/GEO specialist (generative engine optimisation)
- [ ] Build `src/agents/specialists/growth_hacker.py` — referral loops, viral mechanics, retention experiments
- [ ] Build `src/tools/base_tool.py` — abstract base class for all tool wrappers
- [ ] Build `src/tools/tool_registry.py` — database-driven tool activation per brand, budget-aware gating
- [ ] Build `src/tools/custom_adapter.py` — generic REST API adapter (config-driven, supports bearer/API key/basic/OAuth2 auth)
- [ ] Build `src/tools/ads/meta_ads.py` — Meta Ads API (campaigns, bids, spend, Ad Library)
- [ ] Build `src/tools/ads/google_ads.py` — Google Ads API (search, display, shopping campaigns)
- [ ] Build `src/tools/ads/amazon_ads.py` — Amazon Advertising API (sponsored products/brands)
- [ ] Build `src/tools/commerce/shopify.py` — Shopify Admin API (products, orders, inventory)
- [ ] Build `src/tools/commerce/amazon.py` — Amazon Seller Central API (listings, FBA, inventory)
- [ ] Build `src/tools/commerce/blinkit.py` — Blinkit Seller API (quick commerce listings, inventory sync)
- [ ] Build `src/tools/llm_as_tool/chatgpt.py` — OpenAI API for AEO/GEO brand visibility testing
- [ ] Build `src/tools/llm_as_tool/perplexity.py` — Perplexity API for AEO/GEO brand presence testing
- [ ] Build `src/tools/comms/gmail.py` — Gmail API (send, read, draft supplier emails)
- [ ] Build `src/tools/comms/whatsapp.py` — WhatsApp Business API outbound messaging
- [ ] Build `src/tools/logistics/shiprocket.py` — Shiprocket API (order fulfilment, tracking)
- [ ] Build `src/tools/logistics/delhivery.py` — Delhivery API (shipping, pincode serviceability)
- [ ] Build `src/tools/compliance/fssai.py` — FSSAI compliance date tracker
- [ ] Build `src/tools/data/supabase_client.py` — Supabase read/write operations
- [ ] Build `src/tools/data/d2c_benchmarks.py` — proprietary Indian D2C benchmarks database
- [ ] Seed `tool_registry` entries for AIM (active tools) and LembasMax (wind-down subset)
- [ ] Write `SKILLS.md` — reusable agent capabilities (query_meta_ads, send_whatsapp, calculate_roas, check_inventory, test_aeo_visibility, register_custom_api, etc.)
- [ ] Verify heartbeat lifecycle: scheduler triggers agent → agent runs → writes audit → updates ticket → stays within budget
- [ ] Verify tool isolation: agent can only use tools registered for its brand
- [ ] Verify custom adapter: register a mock API via JSON config → agent calls it successfully
- [ ] Verify all agents in AIM brand org chart can execute independently

### Week 4 — Messaging Interface and Production Deploy

Goal: Founder can message via WhatsApp/Telegram and get real answers from agents. System deployed to Hetzner.

- [ ] Build `src/gateway/routes/whatsapp.py` — WhatsApp Business API webhook handler
- [ ] Build `src/gateway/routes/telegram.py` — Telegram Bot API webhook handler
- [ ] Build `src/gateway/intent_router.py` — natural language → brand + agent + task resolution
- [ ] Wire intent router to org chart: "how's AIM doing?" → AIM CEO agent → synthesis task
- [ ] Build fallback path: WhatsApp/Telegram → Gateway directly (when OpenClaw is offline)
- [ ] Build lightweight React admin panel: company list, agent status, budget dashboard, audit log viewer
- [ ] Deploy to Hetzner VPS CX22: Docker Compose with Postgres, Infisical, Gateway, Scheduler
- [ ] Set up Infisical with production secrets (all brand API keys scoped per agent)
- [ ] Configure WhatsApp Business API webhook pointing to Hetzner VPS
- [ ] Configure Telegram Bot webhook pointing to Hetzner VPS
- [ ] Set up systemd service for Gateway + Scheduler (auto-restart on failure)
- [ ] Run full smoke test: send WhatsApp message → Gateway receives → intent routed → agent executes → response sent back via WhatsApp
- [ ] Run full smoke test: heartbeat fires → agent runs autonomously → result visible in admin panel and via WhatsApp query
- [ ] Security audit: verify no cross-brand data leakage, no secrets in logs, sanitizer blocks known injection patterns
- [ ] Document production runbook: deploy, rollback, log access, emergency agent pause

---

## Decision Log

Record architectural decisions here as they are made during development.

| # | Date | Decision | Rationale |
|---|---|---|---|
| 1 | Week 0 | Monorepo with layer-based package structure | Keeps all layers co-located for a solo founder; avoids premature microservice split |
| 2 | Week 0 | Infisical over HashiCorp Vault | Open-source, lighter weight, good SDK, self-hostable on same VPS |
| 3 | Week 0 | APScheduler over Celery | No need for distributed task queue on single VPS; APScheduler is simpler and sufficient |
| 4 | Week 0 | PostgreSQL for audit log (not Supabase) | Audit log must be fully controlled, immutable, and not exposed via Supabase's REST API |
| 5 | Week 0 | Cerebras for non-reasoning tasks | 10-100x faster inference than self-hosted; cost-effective for classification and monitoring |
| 6 | Week 0 | Agent templates instantiated per brand | Avoids code duplication; brand-specific config lives in DB, not in agent source code |
| 7 | Week 0 | Standing + specialist agent model (not fixed org chart) | Brands need different expertise at different stages; permanent headcount for every skill is wasteful; hire-on-demand mirrors real company scaling |
| 8 | Week 0 | Database-driven tool registry, not hardcoded tool access | Which APIs a brand uses depends on budget and channel strategy; tool activation should be a config change, not a code change |
| 9 | Week 0 | Generic custom_adapter.py for arbitrary REST APIs | Avoids writing a new tool module for every vendor; most APIs follow REST patterns and can be handled by config-driven adapter |
| 10 | Week 0 | ChatGPT/Perplexity APIs as tools, not LLM providers | AEO/GEO brand visibility testing is a tool function (testing outputs of other AI systems), not agent reasoning; must not route through model router or pollute LLM budget tracking |

---

## Open Questions

- [ ] **WhatsApp Business API provider:** Use Meta's Cloud API directly or a BSP like Gupshup/Wati? Cloud API is free for first 1,000 conversations/month but requires business verification. Gupshup provides easier onboarding.
- [ ] **Supabase hosting:** Use Supabase Cloud (free tier, 500MB) or self-host on the same Hetzner VPS? Self-hosting saves cost but adds maintenance burden.
- [ ] **OpenClaw protocol:** How does OpenClaw authenticate with the Gateway? Shared API key is simplest; mTLS is more secure but complex for a single founder.
- [ ] **Agent memory:** Should agents have long-term memory (vector store) or operate statelessly with full context from Supabase on each run? Vector store adds complexity; Supabase queries may be sufficient for structured brand data.
- [ ] **LembasMax wind-down automation:** What specific liquidation tasks should LembasMax agents optimise for? (Inventory clearance pricing, final supplier settlements, marketplace delisting timeline?)
- [ ] **React admin panel scope:** Minimal read-only dashboard or full CRUD for company/agent management? Recommend read-only for Week 4, with CRUD added only if WhatsApp interface proves insufficient.
- [ ] **Vapi.ai integration timeline:** Voice interface is marked Phase 2. What triggers the decision to start Phase 2? (e.g., after all WhatsApp workflows are stable for 2 weeks)
- [ ] **Specialist agent budget allocation:** When a specialist is hired, does budget come from the brand's existing agent pool (reducing standing agent budgets) or from a separate "specialist reserve" per brand? Recommend separate reserve to avoid starving standing operations.
- [ ] **Specialist auto-proposal vs manual trigger:** Should the hiring manager proactively scan KPIs and propose hires, or only respond when a standing agent explicitly flags a problem? Proactive is more autonomous but risks unnecessary proposals. Start with manual trigger (standing agent requests), add proactive scan in Phase 2.
- [ ] **AEO/GEO query budget:** ChatGPT and Perplexity API calls cost real money per query. How many brand-visibility test queries per day/week per brand? Need a separate budget line in `tool_registry` for LLM-as-tool costs, distinct from agent reasoning costs.
- [ ] **Blinkit API access:** Blinkit's seller API is not fully public. May require partnership or manual onboarding. Validate API access before building the integration module.
- [ ] **Google Ads complexity:** Google Ads API requires OAuth2 with refresh tokens and has complex campaign structure. Build dedicated module or use custom adapter? Recommend dedicated module due to OAuth complexity.
- [ ] **Shopify vs direct D2C:** Does AIM sell via Shopify or a custom storefront? This determines whether the Shopify tool is relevant for AIM or only for future brands.

---

## Known Risks

| Risk | Impact | Mitigation |
|---|---|---|
| **Hetzner VPS single point of failure** | All agents, Gateway, and scheduler go down if VPS fails | Weekly Postgres backups to S3-compatible storage (Hetzner Object Storage). Systemd auto-restart. Monitor uptime with simple health check cron. |
| **WhatsApp Business API rate limits** | Founder queries or agent outbound messages may be throttled | Implement message queue with backoff. Prioritise founder-initiated messages over agent-initiated. |
| **Cerebras API availability** | If Cerebras is down, all heartbeats and batch tasks stall | Fallback to Anthropic Haiku for monitoring tasks (slightly higher cost, still viable). Implement circuit breaker in `src/llm/cerebras.py`. |
| **Prompt injection via external data** | Malicious content in emails or ad data could hijack agent behaviour | Sanitizer is mandatory for all external data. Defence-in-depth: sanitizer + model-level system prompts that instruct agents to ignore injected instructions. Regular red-team testing of sanitizer. |
| **Budget overrun from runaway agent** | A misconfigured heartbeat or loop could burn through LLM budget | Hard stop in budget enforcer. Per-agent daily and monthly caps. Audit log alerts when agent hits 80% of budget. |
| **Infisical self-hosted maintenance** | Upgrades, backups, and downtime management for secret vault | Pin Infisical version in Docker Compose. Test upgrades in local dev before production. Fallback: environment variables with restricted file permissions (temporary, last resort). |
| **Solo founder bus factor** | If the founder is unavailable, system has no human oversight | Governance layer supports pause-all command via single WhatsApp message. Agents default to safe no-op if governance is unreachable. Document emergency procedures in runbook. |
| **Specialist agent sprawl** | Too many specialists hired across brands could blow through LLM budget | Hard cap on concurrent specialists per brand (recommend 3 max). Budget enforcer treats specialist budget as separate pool with its own ceiling. Hiring manager must include ROI justification in every proposal. |
| **Tool API cost accumulation** | Multiple ad platforms + commerce APIs + AEO/GEO queries add up to significant monthly API costs beyond LLM spend | `tool_registry` tracks per-tool monthly budget caps. Budget enforcer covers both LLM tokens and tool API costs. Monthly cost report from Portfolio CFO agent. |
| **Custom adapter security** | Generic REST adapter could be misconfigured to hit unintended endpoints or leak credentials | All custom adapter configs validated against a strict schema. Credentials always fetched from Infisical (never inline). Audit log records every custom adapter call. Founder must approve new custom tool registrations via governance. |
