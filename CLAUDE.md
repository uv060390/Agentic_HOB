# CLAUDE.md — BrandOS

**BrandOS** is a D2C operating system that runs a house of brands (AIM, LembasMax, future acquisitions) as AI-agent-managed companies under a single human founder, with WhatsApp/Telegram as the primary interface.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Founder Layer                                      │
│   OpenClaw (founder's machine) → WhatsApp / Telegram        │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Gateway Layer                                      │
│   FastAPI on Hetzner VPS — webhooks, auth, rate limiting,   │
│   prompt injection sanitizer, intent router                 │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: Orchestration Layer (BrandOS Core)                 │
│   Company registry, org charts, goal ancestry, heartbeat    │
│   scheduler, budget enforcer, model router, audit log,      │
│   ticket system, governance controls,                       │
│   workflow orchestrator (multi-agent pipelines)             │
├─────────────────────────────────────────────────────────────┤
│ Layer 4: Secret Vault Layer                                 │
│   Infisical (self-hosted) — per-brand, per-agent scoping    │
├─────────────────────────────────────────────────────────────┤
│ Layer 5: Agent Layer                                        │
│   HoldCo agents + per-brand standing teams (CEO, CMO,       │
│   Scout, Creative, Performance, Ops, Finance)               │
│   + Specialist agents hired on-demand (Data Scientist,      │
│     Engineer, Data Analyst, SEO/AEO, etc.) — spun up when   │
│     a business problem demands it, wound down after         │
├─────────────────────────────────────────────────────────────┤
│ Layer 6: Tool Layer                                         │
│   Ads: Meta, Google, Amazon, Shopify, Blinkit              │
│   Commerce: Amazon Seller Central, Shopify, Blinkit, Lovable AI │
│   LLM-as-Tool: ChatGPT API (AEO/GEO), Perplexity          │
│   Logistics: Shiprocket, Delhivery                          │
│   Comms: Gmail, WhatsApp Business                           │
│   Compliance: FSSAI calendar                                │
│   Data: Supabase, D2C benchmarks DB                         │
│   Storage: Google Drive (Creative Library)                  │
│   Custom: pluggable adapter for any 3rd-party REST API      │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Infrastructure | Hetzner VPS CX22 (~₹500/month) |
| Backend | Python 3.11 + FastAPI |
| Scheduling | APScheduler (server-side, in-process) |
| Primary database | PostgreSQL 15 (audit log, tickets, org structure) |
| Brand/agent data | Supabase (Postgres + REST + Realtime) |
| Secret management | Infisical (self-hosted on same VPS) |
| LLM: reasoning | Anthropic API — Claude Opus (strategy/synthesis), Claude Sonnet (creative/analysis) |
| LLM: speed/cost | Cerebras API — Llama 3.3 70B (batch/classification), Llama 3.1 8B (monitoring/heartbeats) |
| Frontend | React (lightweight admin panel, secondary to messaging) |
| Personal interface | OpenClaw (runs on founder's machine) |
| Messaging | WhatsApp Business API + Telegram Bot API |
| Voice (Phase 2) | Vapi.ai |

---

## Repository Structure

```
brandos/
├── CLAUDE.md                   # This file — read first every session
├── PLAN.md                     # Build sequence, status, next actions
├── AGENTS.md                   # Per-agent definitions (created Week 2)
├── SKILLS.md                   # Reusable agent capabilities (created Week 3)
├── pyproject.toml              # Project metadata, dependencies (uv/pip)
├── docker-compose.yml          # Local dev: Postgres, Infisical, Supabase
├── Dockerfile                  # Production deployment
├── alembic/                    # Database migrations
│   ├── alembic.ini
│   └── versions/
├── src/
│   ├── gateway/                # Layer 2: Gateway
│   │   ├── __init__.py
│   │   ├── app.py              # FastAPI application entry point
│   │   ├── routes/
│   │   │   ├── whatsapp.py     # WhatsApp webhook handler
│   │   │   ├── telegram.py     # Telegram webhook handler
│   │   │   └── vapi.py         # Voice webhook handler (Phase 2)
│   │   ├── auth.py             # API key validation, rate limiting
│   │   ├── sanitizer.py        # Prompt injection sanitizer
│   │   └── intent_router.py    # Routes intent → brand → agent → task
│   ├── core/                   # Layer 3: Orchestration (BrandOS Core)
│   │   ├── __init__.py
│   │   ├── company_registry.py # Brand CRUD, isolation boundaries
│   │   ├── org_chart.py        # Agent hierarchy and reporting lines
│   │   ├── goal_ancestry.py    # Task → project → company → mission tracing
│   │   ├── heartbeat.py        # APScheduler heartbeat definitions
│   │   ├── budget_enforcer.py  # Token usage tracking, hard limits
│   │   ├── model_router.py     # Model/provider selection per task
│   │   ├── audit_log.py        # Immutable Postgres audit log
│   │   ├── ticket_system.py    # Threaded conversation/decision tracking
│   │   ├── governance.py       # Approve, override, pause, rollback
│   │   └── orchestrator.py     # Multi-agent workflow engine (step sequencing, data passing)
│   ├── vault/                  # Layer 4: Secret Vault
│   │   ├── __init__.py
│   │   ├── client.py           # Infisical SDK wrapper
│   │   └── sandbox.py          # Mock credentials for dev/test
│   ├── agents/                 # Layer 5: Agent Layer
│   │   ├── __init__.py
│   │   ├── base_agent.py       # Abstract base class for all agents
│   │   ├── holdco/             # Cross-brand agents
│   │   │   ├── portfolio_cfo.py
│   │   │   └── bd_agent.py
│   │   ├── templates/          # Brand-level standing agent templates
│   │   │   ├── ceo.py
│   │   │   ├── cmo.py
│   │   │   ├── scout.py
│   │   │   ├── creative.py
│   │   │   ├── performance.py
│   │   │   ├── ops.py
│   │   │   └── finance.py
│   │   ├── specialists/        # On-demand specialist agent templates
│   │   │   ├── __init__.py
│   │   │   ├── data_scientist.py   # ML model building, CAC optimisation, LTV prediction
│   │   │   ├── engineer.py         # Ad tech pipelines, data infra, automation scripts
│   │   │   ├── data_analyst.py     # Deep-dive analysis, cohort breakdowns, funnel diagnostics
│   │   │   ├── seo_aeo.py          # SEO + AEO/GEO (generative engine optimisation via ChatGPT API)
│   │   │   ├── growth_hacker.py    # Referral loops, viral mechanics, retention experiments
│   │   │   └── optimizer.py        # Creative optimisation meta-specialist (triggers workflows, evaluates quality)
│   │   ├── hiring_manager.py   # Evaluates brand KPIs → recommends specialist hires
│   │   └── registry.py         # Agent instantiation per brand (standing + specialist)
│   ├── tools/                  # Layer 6: Tool Layer
│   │   ├── __init__.py
│   │   ├── base_tool.py        # Abstract base class for all tool wrappers
│   │   ├── custom_adapter.py   # Generic REST API adapter — pluggable for any 3rd-party API
│   │   ├── tool_registry.py    # Registers available tools per brand, budget-aware activation
│   │   ├── ads/                # Advertising platforms
│   │   │   ├── __init__.py
│   │   │   ├── meta_ads.py     # Meta Ads API (campaigns, bids, spend, Ad Library)
│   │   │   ├── google_ads.py   # Google Ads API (search, display, shopping)
│   │   │   └── amazon_ads.py   # Amazon Advertising API (sponsored products/brands)
│   │   ├── commerce/           # Sales channels
│   │   │   ├── __init__.py
│   │   │   ├── shopify.py      # Shopify Admin API (products, orders, inventory)
│   │   │   ├── lovable_shopify.py  # Lovable AI storefront builder (creates Shopify pages via prompts)
│   │   │   ├── lovable_prompt_builder.py  # Assembles brand-aware prompts for Lovable
│   │   │   ├── amazon.py       # Amazon Seller Central API (listings, FBA)
│   │   │   └── blinkit.py      # Blinkit Seller API (quick commerce listings, inventory)
│   │   ├── llm_as_tool/        # LLMs used as tools by agents (not for agent reasoning)
│   │   │   ├── __init__.py
│   │   │   ├── chatgpt.py      # OpenAI API — AEO/GEO: test brand visibility in AI answers
│   │   │   └── perplexity.py   # Perplexity API — AEO/GEO: test brand presence in search AI
│   │   ├── comms/              # Communications
│   │   │   ├── __init__.py
│   │   │   ├── gmail.py        # Gmail API (supplier emails, investor updates)
│   │   │   └── whatsapp.py     # WhatsApp Business API (outbound customer/supplier comms)
│   │   ├── logistics/          # Shipping and fulfilment
│   │   │   ├── __init__.py
│   │   │   ├── shiprocket.py   # Shiprocket API (order fulfilment, tracking)
│   │   │   └── delhivery.py    # Delhivery API (shipping, pincode serviceability)
│   │   ├── compliance/         # Regulatory
│   │   │   ├── __init__.py
│   │   │   └── fssai.py        # FSSAI compliance calendar and renewal tracker
│   │   ├── data/               # Data sources
│   │   │   ├── __init__.py
│   │   │   ├── supabase_client.py  # Supabase read/write for brand/agent data
│   │   │   └── d2c_benchmarks.py   # Proprietary Indian D2C benchmarks database
│   │   ├── storage/            # Storage tools
│   │   │   ├── __init__.py
│   │   │   └── google_drive.py # Creative Library — Google Drive for creatives + CTR metadata
│   │   └── custom/             # Brand-specific custom integrations
│   │       ├── __init__.py
│   │       └── README.md       # How to add a new custom tool via custom_adapter.py
│   ├── llm/                    # LLM abstraction
│   │   ├── __init__.py
│   │   ├── provider.py         # Unified interface: call(model, messages, ...)
│   │   ├── anthropic.py        # Anthropic API client
│   │   └── cerebras.py         # Cerebras API client
│   └── shared/                 # Cross-cutting utilities
│       ├── __init__.py
│       ├── config.py           # Pydantic Settings loader
│       ├── db.py               # SQLAlchemy engine + session
│       ├── schemas.py          # Shared Pydantic models
│       └── exceptions.py       # Custom exception hierarchy
├── tests/
│   ├── conftest.py             # Shared fixtures (test DB, mock vault)
│   ├── unit/
│   │   ├── test_sanitizer.py
│   │   ├── test_model_router.py
│   │   ├── test_budget_enforcer.py
│   │   └── ...
│   ├── integration/
│   │   ├── test_gateway.py
│   │   ├── test_agent_lifecycle.py
│   │   └── ...
│   └── fixtures/
│       └── ...
└── scripts/
    ├── seed_companies.py       # Seed AIM + LembasMax into registry
    ├── seed_agents.py          # Seed agent definitions per brand
    └── run_heartbeat.py        # Manual heartbeat trigger for testing
```

---

## Key Conventions

### Naming

- **Files and modules:** `snake_case.py`
- **Classes:** `PascalCase` (e.g. `BaseAgent`, `ModelRouter`, `BudgetEnforcer`)
- **Functions:** `snake_case` (e.g. `route_model`, `enforce_budget`)
- **Database tables:** `snake_case`, singular (e.g. `audit_entry`, `agent_config`, `company`)
- **Environment variables:** `SCREAMING_SNAKE_CASE` prefixed by domain (e.g. `BRANDOS_DB_URL`, `INFISICAL_TOKEN`)
- **API routes:** kebab-case under versioned prefix (e.g. `/api/v1/agent-status`)
- **Brand identifiers:** lowercase slug (e.g. `aim`, `lembasmax`)

### File Structure

- All source code lives under `src/`. No logic in the project root.
- Each architectural layer maps to one top-level package under `src/`.
- **Standing agents** (`src/agents/templates/`) are the permanent org chart — always active for a brand. **Specialist agents** (`src/agents/specialists/`) are hired on-demand when a specific business problem requires expertise beyond the standing team, and wound down once the problem is resolved.
- Agent templates define the agent's role, tools, model tier, and heartbeat schedule — they are instantiated per brand by the registry.
- Tools are organised by domain under `src/tools/` (ads, commerce, logistics, comms, compliance, data). Each brand only activates the tools it needs — governed by `tool_registry.py` and constrained by the brand's budget.
- The `custom_adapter.py` provides a generic REST API adapter. Any third-party API can be integrated without writing a new tool module — just provide a config with base URL, auth method, and endpoint definitions.
- Shared utilities go in `src/shared/`. Do not duplicate DB sessions, config loading, or exception classes across layers.

### API Design Patterns

- Every Gateway endpoint validates auth before any processing.
- Every request that reaches an agent must first pass through the prompt injection sanitizer.
- All API responses use a consistent envelope: `{ "ok": bool, "data": ..., "error": ... }`.
- Use Pydantic models for all request/response validation — no raw dicts.
- Long-running agent tasks return a ticket ID immediately; results are polled or pushed via webhook.

### Database Schema Patterns

- All tables include `id` (UUID), `created_at`, `updated_at`.
- `audit_entry` is append-only. No UPDATE or DELETE operations ever.
- `company` table stores brand metadata; `agent_config` references `company_id`.
- Token usage tracked in `token_usage` table: `agent_id`, `company_id`, `model`, `input_tokens`, `output_tokens`, `cost_usd`, `timestamp`.
- `tool_registry` table: maps which tools are active for which brand. Columns: `company_id`, `tool_slug`, `is_active`, `monthly_budget_cap_usd`. A tool module existing in code does not make it available — it must have an active registry entry.
- `tool_config` table: stores custom API adapter configs per brand. Columns: `company_id`, `tool_slug`, `config_json`, `secret_ref`. Used by `custom_adapter.py`.
- `specialist_hire` table: tracks on-demand specialist agent lifecycle. Columns: `company_id`, `specialist_type`, `status` (proposed/approved/active/wound_down), `problem_statement`, `success_criteria`, `budget_allocated`, `budget_spent`, `approved_by`, `activated_at`, `wound_down_at`.
- `workflow_run` table: tracks orchestrator workflow executions. Columns: `id`, `workflow_name`, `company_id`, `status`, `parent_ticket_id`, `step_outputs` (JSONB), `started_at`, `completed_at`, `error`.
- `workflow_step` table: individual step states within a workflow run. Columns: `id`, `run_id`, `step_index`, `agent_template`, `task_subtype`, `status`, `output`, `started_at`, `completed_at`.
- `creative_library` table: metadata for creative assets stored in Google Drive. Columns: `id`, `brand_slug`, `source` (competitor|original), `competitor_brand`, `predicted_ctr`, `actual_ctr` (updated retroactively by Performance agent), `creative_type`, `file_url`, `created_by_agent`, `workflow_run_id`, `created_at`, `updated_at`.
- Every agent action that changes state writes to `audit_entry` before returning.

### Model Router Rules

| Task Type | Model | Provider |
|---|---|---|
| Strategy, synthesis, planning | Claude Opus | Anthropic |
| Creative generation, analysis | Claude Sonnet | Anthropic |
| Batch processing, classification | Llama 3.3 70B | Cerebras |
| Routine monitoring, heartbeat checks | Llama 3.1 8B | Cerebras |

The model router (`src/core/model_router.py`) is called before every LLM invocation. Agents do not choose their own model — the router decides based on task type.

### Specialist Agent Hiring System

The standing org chart (CEO, CMO, Scout, etc.) handles day-to-day operations. But when a brand hits a specific problem that the standing team can't solve — CAC spiking, conversion funnels breaking, a new channel launch — the system can **hire specialist agents on demand**.

How it works:

1. **Detection:** A standing agent (usually CEO or Finance) identifies a KPI anomaly or strategic need during a heartbeat. Alternatively, the `hiring_manager.py` runs periodic diagnostics against brand KPIs.
2. **Proposal:** The hiring manager generates a hiring proposal: which specialist(s), what problem they'll solve, estimated token budget, expected duration, and success criteria.
3. **Approval:** Proposal goes through governance — founder approves via WhatsApp/Telegram. No specialist is hired without explicit founder approval.
4. **Instantiation:** The registry spins up the specialist agent(s) with their own budget allocation, tool access, and heartbeat schedule — all scoped to the requesting brand.
5. **Execution:** Specialists work autonomously within their budget. They report to the CEO agent and write to the ticket system like any standing agent.
6. **Wind-down:** When the success criteria are met or the budget is exhausted, the specialist agent is deactivated. Its outputs remain in the audit log and Supabase.

Example scenarios:

- **CAC crisis:** Performance agent flags CAC up 40% MoM → hiring manager proposes Data Scientist + Data Analyst → they build a bid optimisation model, identify wasted spend segments, and retrain targeting → CAC normalises → specialists wound down.
- **New channel launch (Blinkit):** CEO agent decides to expand to quick commerce → hiring manager proposes Engineer + Data Analyst → Engineer builds Blinkit API integration, Analyst sets up inventory tracking and demand forecasting → channel is live and handed to Ops agent → specialists wound down.
- **AEO/GEO push:** CMO identifies brand is invisible in ChatGPT and Perplexity answers → hiring manager proposes SEO/AEO specialist → specialist audits brand presence across AI engines, creates content strategy, tests via ChatGPT API and Perplexity API → playbook handed to Creative agent → specialist wound down.

Specialist agents use the same `base_agent.py`, same LLM provider, same budget enforcer, same audit log. They are not special — they just have specialised system prompts, tool access, and a finite lifespan.

### Multi-Agent Workflow Orchestration

Agents do not call each other directly. All inter-agent pipelines run through `src/core/orchestrator.py`.

**How it works:**

1. A `Workflow` is a named, ordered list of `WorkflowStep` objects. Each step defines: `agent_template`, `task_subtype`, and an optional `context_key` to capture output for the next step.
2. `run_workflow(workflow_name, company_slug, initial_context)` executes steps sequentially. Each step's `AgentResult.output` is passed as `context["prev_output"]` to the next step.
3. Workflows are registered in `WORKFLOW_REGISTRY` in `orchestrator.py`. Adding a new workflow is a code change to the registry, not to individual agents.
4. The `WorkflowRun` result (including per-step outputs) is persisted to the `workflow_run` and `workflow_step` tables for auditability.

**Registered workflows:**

| Workflow | Steps | Trigger |
|---|---|---|
| `creative_optimisation` | engineer.build_scraper → data_scientist.rank_creatives → creative.replicate_top_ads → optimizer.evaluate_quality | Scout flags creative staleness or CTR drop |
| `competitor_intelligence` | scout.competitor_scan → data_analyst.attribution_analysis → cmo.campaign_brief | CMO requests competitive brief |

**Agent delegation (`BaseAgent.delegate()`):**

For ad-hoc cross-agent task delegation (outside of a registered workflow), agents use `self.delegate(task_subtype, target_agent_template, context)`. This method:
- Resolves the target agent instance from the registry (scoped to the same `company_id`)
- Calls `agent.run(task)` on the resolved instance
- Returns an `AgentResult` — the caller can use it or ignore it
- Always preserves brand isolation: delegation across brands is forbidden

The Optimizer specialist agent uses `trigger_workflow` to launch the `creative_optimisation` pipeline and `evaluate_quality` to LLM-judge whether the output meets the objective. If it does not, it iterates (re-triggers the relevant step) or winds down.

**Creative Library feedback loop:**

1. Creative agent saves outputs to `src/tools/storage/google_drive.py` via `save_creative()` — file to Google Drive, metadata to `creative_library` table.
2. Performance agent retroactively calls `update_actual_ctr(creative_id, actual_ctr)` after each ad campaign flight, closing the prediction-vs-reality loop.
3. On the next `creative_optimisation` workflow run, `get_top_creatives()` sorts by `actual_ctr` (not `predicted_ctr`) when actual data is available, so the model improves over time.

---

### Tool Layer Design

Tools are organised by domain and activated per brand based on need and budget. Not every brand needs every tool.

**Tool activation is database-driven.** The `tool_registry` table maps which tools are active for which brand. Adding a new tool to a brand is a database insert, not a code change.

**Custom API adapter.** For any third-party REST API not covered by a built-in tool module, `custom_adapter.py` provides a generic wrapper. A brand can integrate with any API by providing a JSON config:

```python
# Example: Integrating a custom CRM API for a brand
{
    "tool_slug": "brand_crm",
    "base_url": "https://api.somecrm.com/v1",
    "auth_type": "bearer",          # bearer | api_key_header | basic | oauth2
    "secret_ref": "aim/crm_token",  # Infisical path — scoped to brand
    "endpoints": {
        "get_contacts": { "method": "GET", "path": "/contacts", "params": ["limit", "offset"] },
        "create_deal":  { "method": "POST", "path": "/deals", "body_schema": "..." }
    }
}
```

This config is stored in the `tool_config` table per brand. The custom adapter reads it at runtime, injects credentials from Infisical, and exposes the endpoints as callable tools for agents.

**LLM-as-Tool distinction.** ChatGPT API and Perplexity API are used as *tools* — meaning agents call them to check brand visibility in AI-generated answers (AEO/GEO). They are **not** used for agent reasoning. Agent reasoning goes through the model router. This is an important distinction: the ChatGPT API key goes in the Tool Layer, not the LLM Layer.

---

## What Claude Code Must NEVER Do

1. **Never use a premium model for a heartbeat check.** Heartbeats and routine monitoring use Llama 3.1 8B via Cerebras. Wasting Claude Opus tokens on a status ping is a budget violation.
2. **Never store secrets in `.env` files, code, or config files.** All secrets are fetched at runtime from Infisical via `src/vault/client.py`. The only exception is `INFISICAL_TOKEN` itself, which is set as a system-level environment variable on the VPS.
3. **Never skip the prompt injection sanitizer.** Every piece of external data (email content, ad platform responses, supplier messages, webhook payloads) must pass through `src/gateway/sanitizer.py` before entering any agent's context window. No exceptions.
4. **Never allow cross-brand data access.** AIM agents must never see LembasMax credentials, data, or context — and vice versa. Brand isolation is enforced at the vault layer and the company registry. Do not write queries that join across brands without explicit governance approval.
5. **Never let an agent call an LLM directly.** All LLM calls go through `src/llm/provider.py`, which checks the model router and budget enforcer. No raw `anthropic.Anthropic()` or `requests.post()` to an LLM endpoint from agent code.
6. **Never make the system dependent on the founder's machine being online.** All heartbeats, scheduled tasks, and agent execution run server-side via APScheduler. OpenClaw is a convenience interface, not infrastructure.
7. **Never create a database migration that modifies `audit_entry` rows.** The audit log is immutable. Migrations may add columns but must never UPDATE or DELETE existing data.
8. **Never hardcode brand-specific logic.** Agent templates are generic. Brand-specific configuration (goals, budgets, active tools, wind-down mode) lives in the database, not in code.
9. **Never hire a specialist agent without governance approval.** Specialist agents cost budget. The hiring manager proposes, the founder approves. No code path should auto-instantiate a specialist without a governance gate.
10. **Never activate a tool for a brand without a `tool_registry` entry.** Even if a tool module exists in code, it is not available to a brand's agents unless the brand has an active entry in the `tool_registry` table. Tools are budget-gated.
11. **Never route AEO/GEO queries through the model router.** ChatGPT API and Perplexity API calls are tool invocations (checking brand visibility), not agent reasoning. They go through `src/tools/llm_as_tool/`, not `src/llm/provider.py`. Do not confuse these two paths.
12. **Never build a one-off tool integration.** If a brand needs to call a new API, use `custom_adapter.py` with a JSON config stored in `tool_config`. Only build a dedicated tool module (like `meta_ads.py`) if the integration is complex enough to warrant it (OAuth flows, pagination, webhook subscriptions).
13. **Never chain agents by calling them directly from another agent.** All multi-agent pipelines run through `src/core/orchestrator.py`. Direct agent-to-agent calls (e.g. `CreativeAgent().run()` inside `ScoutAgent.run()`) bypass audit logging, budget enforcement, and step isolation. Use `self.delegate()` or `run_workflow()` instead.
14. **Never discard creative agent output without saving it to the Creative Library.** Every piece of creative output (ad copy, creative brief, replicated competitor ad) must be saved via `src/tools/storage/google_drive.py`. This is the source of truth for the performance feedback loop — if it is not saved, the system cannot learn from it.

---

## Running the Project Locally

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (for Postgres, Infisical)
- Node.js 18+ (for React frontend, optional)

### Setup

```bash
# Clone and enter repo
git clone <repo-url> && cd brandos

# Create virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Start local services (Postgres, Infisical)
docker-compose up -d

# Run database migrations
alembic upgrade head

# Seed initial data
python scripts/seed_companies.py
python scripts/seed_agents.py

# Start the Gateway server
uvicorn src.gateway.app:app --reload --port 8000
```

### Useful Commands

```bash
# Run heartbeat scheduler standalone (for testing)
python scripts/run_heartbeat.py

# Format code
ruff format src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

---

## Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only (requires docker-compose services running)
pytest tests/integration/

# With coverage
pytest --cov=src --cov-report=term-missing

# Single test file
pytest tests/unit/test_sanitizer.py -v
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `BRANDOS_DB_URL` | PostgreSQL connection string for primary database |
| `BRANDOS_SUPABASE_URL` | Supabase project URL |
| `BRANDOS_SUPABASE_KEY` | Supabase service role key (not anon key) |
| `INFISICAL_TOKEN` | Machine identity token for Infisical vault access |
| `INFISICAL_HOST` | Infisical server URL (default: `http://localhost:8080`) |
| `ANTHROPIC_API_KEY` | Anthropic API key (stored in Infisical in production, env var for local dev only) |
| `CEREBRAS_API_KEY` | Cerebras API key (stored in Infisical in production, env var for local dev only) |
| `OPENAI_API_KEY` | OpenAI API key for ChatGPT AEO/GEO tool (stored in Infisical, scoped per brand) |
| `PERPLEXITY_API_KEY` | Perplexity API key for AEO/GEO tool (stored in Infisical, scoped per brand) |
| `WHATSAPP_VERIFY_TOKEN` | WhatsApp webhook verification token |
| `WHATSAPP_API_TOKEN` | WhatsApp Business API access token |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token |
| `GATEWAY_API_KEY` | API key for OpenClaw → Gateway authentication |
| `BRANDOS_ENV` | Environment: `development`, `staging`, `production` |
| `LOG_LEVEL` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `GOOGLE_DRIVE_SERVICE_ACCOUNT` | Path to Google Drive service account JSON (local dev only; stored in Infisical in production) |
| `GOOGLE_DRIVE_CREATIVE_FOLDER_ID` | Google Drive folder ID for Creative Library root (one per brand, stored in `agent_config.config_json`) |

In production, only `INFISICAL_TOKEN`, `INFISICAL_HOST`, `BRANDOS_DB_URL`, `BRANDOS_ENV`, and `LOG_LEVEL` are set as system environment variables. All other secrets are fetched from Infisical at runtime.

---

## Related Documentation

| File | When to Read |
|---|---|
| `PLAN.md` | At session start — check current week, status, and next task |
| `AGENTS.md` | When implementing or modifying any agent (created Week 2) |
| `SKILLS.md` | When adding a reusable capability to an agent (created Week 3) |
