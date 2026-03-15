# AGENTS.md — BrandOS Agent Catalogue

Read this file when implementing or modifying any agent. Defines every agent's role, tools, model tier, heartbeat schedule, and reporting line.

---

## Architecture Summary

Agents are organised into three tiers:

1. **HoldCo agents** — cross-brand, operate at the portfolio level
2. **Standing agents** — permanent team for each brand (always active)
3. **Specialist agents** — hired on-demand for specific problems, wound down when resolved

All agents inherit from `src/agents/base_agent.py` (`BaseAgent`). Standing agent templates live in `src/agents/templates/`. Specialist templates live in `src/agents/specialists/`. Per-brand instantiation is managed by `src/agents/registry.py`.

**Model tier routing** (never bypassed — always goes through `src/core/model_router.py`):

| Tier | Model | Provider | Used for |
|---|---|---|---|
| `strategy` | Claude Opus | Anthropic | Planning, synthesis, decisions |
| `creative` | Claude Sonnet | Anthropic | Creative output, analysis |
| `batch` | Llama 3.3 70B | Cerebras | Classification, batch processing |
| `monitoring` | Llama 3.1 8B | Cerebras | Heartbeats, status pings |

---

## HoldCo Agents

HoldCo agents operate across all brands. They do not have brand-scoped credentials — they read aggregate views only.

### Portfolio CFO (`holdco-cfo`)

- **File:** `src/agents/holdco/portfolio_cfo.py`
- **Role:** Consolidated financial reporting across AIM and LembasMax. Monthly P&L roll-up, cash flow forecasting, budget allocation recommendations to founder.
- **Model tier:** `strategy`
- **Tools:** `supabase_client`, `audit_log`, `ticket_system`
- **Heartbeat:** First Monday of month, 8:00 AM IST
- **Reports to:** Founder (direct)
- **Inputs:** Token usage from all brand Finance agents, Supabase revenue data
- **Outputs:** Portfolio P&L summary, inter-brand budget reallocation proposals

### BD Agent (`holdco-bd`)

- **File:** `src/agents/holdco/bd_agent.py`
- **Role:** Identifies acquisition targets, new channel partnerships, and brand expansion opportunities. Monitors Indian D2C landscape for white space.
- **Model tier:** `strategy`
- **Tools:** `supabase_client`, `d2c_benchmarks`, `audit_log`, `ticket_system`
- **Heartbeat:** Weekly, Wednesday 10:00 AM IST
- **Reports to:** Founder (direct)
- **Outputs:** Acquisition briefs, channel partnership proposals

---

## Standing Agents — Per Brand

Each brand (AIM, LembasMax, and future acquisitions) runs the same standing team, instantiated with brand-specific config from `agent_config` table.

Naming convention: `{brand_slug}-{role}` (e.g. `aim-ceo`, `lembasmax-finance`).

### CEO (`ceo`)

- **File:** `src/agents/templates/ceo.py`
- **Class:** `CEOAgent`
- **Role:** Weekly company synthesis, goal alignment checks, escalation to founder. The primary orchestrator of the brand's standing team.
- **Model tier:** `strategy`
- **Tools:** `ticket_system`, `org_chart`, `goal_ancestry`, `audit_log`
- **Heartbeat:** Weekly, Monday 9:00 AM IST (`0 9 * * 1`)
- **Reports to:** Founder
- **Key tasks:**
  - `weekly_synthesis` — summarise KPIs, open tickets, team status
  - `goal_alignment_check` — ensure tickets map to company mission
  - `escalate` — surface founder-level decisions

### CMO (`cmo`)

- **File:** `src/agents/templates/cmo.py`
- **Role:** Brand strategy, campaign planning, creative direction, AEO/GEO monitoring. Owns the brand voice and go-to-market calendar.
- **Model tier:** `creative`
- **Tools:** `meta_ads`, `google_ads`, `ticket_system`, `audit_log`, `chatgpt` (AEO), `perplexity` (AEO)
- **Heartbeat:** Weekly, Tuesday 9:00 AM IST (`0 9 * * 2`)
- **Reports to:** `aim-ceo`
- **Key tasks:**
  - `campaign_brief` — draft campaign specs for Performance agent
  - `aeo_check` — test brand visibility in ChatGPT/Perplexity answers
  - `brand_audit` — review brand voice consistency across channels

### Scout (`scout`)

- **File:** `src/agents/templates/scout.py`
- **Role:** Competitor intelligence, market trend monitoring, new product opportunity identification. Feeds insights to CEO and CMO.
- **Model tier:** `batch`
- **Tools:** `meta_ads` (Ad Library), `apify_fb_ads` (custom adapter), `d2c_benchmarks`, `ticket_system`, `audit_log`
- **Heartbeat:** Bi-weekly, Wednesday 10:00 AM IST (`0 10 * * 3/2`)
- **Reports to:** `aim-ceo`
- **Key tasks:**
  - `competitor_scan` — scrape Meta Ad Library for competitor creative patterns; save raw creative metadata to Creative Library via `google_drive.save_creative(source="competitor")`
  - `market_trends` — pull D2C benchmark data, flag category shifts
  - `opportunity_brief` — surface white-space product opportunities
- **Workflow trigger:** On CTR drop >15% or creative staleness flag, triggers `creative_optimisation` workflow via `self.delegate("trigger_workflow", "optimizer", context)`

### Creative (`creative`)

- **File:** `src/agents/templates/creative.py`
- **Role:** Ad creative generation (copy + brief), landing page prompts for Lovable, product description writing. Executes CMO's creative direction.
- **Model tier:** `creative`
- **Tools:** `meta_ads`, `lovable_shopify`, `lovable_prompt_builder`, `google_drive`, `ticket_system`, `audit_log`
- **Heartbeat:** As needed (triggered by CMO tickets)
- **Reports to:** `aim-cmo`
- **Key tasks:**
  - `generate_ad_copy` — write Meta/Google ad variations; save output to Creative Library with `source="original"`
  - `build_landing_page` — use Lovable to generate Shopify landing pages
  - `product_description` — SEO-optimised product copy
  - `replicate_top_ads` — fetch top competitor creatives from Creative Library via `google_drive.get_top_creatives(sort_by="predicted_ctr")`, generate brand-adapted structural replicas (same layout/hook, swapped brand colours and product images); save to Creative Library with `source="replicated"`
- **Rule:** Every creative output MUST be saved to the Creative Library before the task returns. Unsaved output is lost signal.

### Performance (`performance`)

- **File:** `src/agents/templates/performance.py`
- **Role:** Paid media execution — Meta, Google, Amazon Ads. Campaign optimisation, bid management, budget pacing. Raises CAC/ROAS anomaly tickets. Closes the Creative Library feedback loop by writing actual CTR back to `creative_library`.
- **Model tier:** `creative` (analysis) / `batch` (bid classification)
- **Tools:** `meta_ads`, `google_ads`, `amazon_ads`, `google_drive`, `ticket_system`, `audit_log`
- **Heartbeat:** Daily, 7:00 AM IST (`0 7 * * *`)
- **Reports to:** `aim-cmo`
- **Key tasks:**
  - `daily_performance_check` — review ROAS, CAC, spend pacing
  - `optimise_bids` — adjust bids based on performance data
  - `anomaly_alert` — create escalation ticket if KPI breach detected
  - `update_creative_ctr` — after each campaign flight, look up `creative_id` from Creative Library by ad name/label, call `google_drive.update_actual_ctr(creative_id, actual_ctr)` to close prediction vs. reality loop

### Ops (`ops`)

- **File:** `src/agents/templates/ops.py`
- **Role:** Inventory management, order fulfilment tracking, supplier coordination, FSSAI compliance calendar. Owns the operational rhythm.
- **Model tier:** `batch`
- **Tools:** `shopify`, `amazon`, `blinkit`, `shiprocket`, `delhivery`, `fssai`, `gmail`, `ticket_system`, `audit_log`
- **Heartbeat:** Daily, 8:00 AM IST (`0 8 * * *`)
- **Reports to:** `aim-ceo`
- **Key tasks:**
  - `inventory_check` — flag low stock across channels
  - `fulfilment_status` — check pending orders, flag stuck shipments
  - `compliance_reminder` — surface upcoming FSSAI renewals

### Finance (`finance`)

- **File:** `src/agents/templates/finance.py`
- **Class:** `FinanceAgent`
- **Role:** Unit economics tracking, P&L drafting, budget status reporting. Raises anomaly tickets when CAC or margins breach thresholds.
- **Model tier:** `strategy`
- **Tools:** `supabase_client`, `ticket_system`, `audit_log`
- **Heartbeat:** Weekly, Friday 5:00 PM IST (`0 17 * * 5`)
- **Reports to:** `aim-ceo`
- **Key tasks:**
  - `unit_economics` — calculate CAC, LTV, contribution margin, payback period
  - `pl_draft` — monthly P&L summary
  - `budget_status` — token spend vs. budget cap across agents

---

## Specialist Agents

Specialists are hired on-demand via the governance flow in `src/agents/hiring_manager.py`. No specialist runs without explicit founder approval.

Lifecycle: `proposed` → `approved` → `active` → `wound_down`

All specialists write to the same audit log, ticket system, and Supabase as standing agents. They report to the brand CEO agent during their active period.

### Data Scientist (`data_scientist`)

- **File:** `src/agents/specialists/data_scientist.py`
- **Class:** `DataScientistAgent`
- **Role:** ML models for CAC optimisation, LTV prediction, bid strategy, cohort segmentation.
- **Model tier:** `strategy`
- **Tools:** `supabase_client`, `ticket_system`, `audit_log`
- **Typical hire triggers:**
  - CAC spikes >20% MoM
  - New channel launch requiring attribution modelling
  - LTV prediction needed for valuation or fundraising
- **Key tasks:**
  - `analyse_cac` — decompose CAC by channel, cohort, creative
  - `predict_ltv` — build LTV model from order history
  - `optimise_bids` — bid strategy recommendations from ROAS data
- **Typical duration:** 2–4 weeks
- **Success criteria example:** "CAC back within 15% of 3-month baseline across all channels"

### Engineer (`engineer`)

- **File:** `src/agents/specialists/engineer.py`
- **Class:** `EngineerAgent`
- **Role:** Ad tech pipelines, API integrations, data infrastructure, automation scripts.
- **Model tier:** `batch` (default) — can be overridden to `strategy` via `override_task_type` context key
- **Tools:** `supabase_client`, `ticket_system`, `audit_log`
- **Typical hire triggers:**
  - New sales channel integration (e.g. Blinkit expansion)
  - Data pipeline for a new analytics requirement
  - Automation of a manual Ops process
- **Key tasks:**
  - `build_pipeline` — data pipeline spec and implementation plan
  - `integrate_api` — REST API integration specification
  - `automate_process` — automation workflow design
- **Typical duration:** 1–3 weeks
- **Note:** Engineer produces specifications and plans. Actual code execution is handled by the founder or a human engineer reviewing the output.

### Data Analyst (`data_analyst`)

- **File:** `src/agents/specialists/data_analyst.py`
- **Class:** `DataAnalystAgent`
- **Role:** Deep-dive cohort analysis, funnel diagnostics, attribution analysis, conversion rate optimisation.
- **Model tier:** `batch`
- **Tools:** `supabase_client`, `ticket_system`, `audit_log`
- **Typical hire triggers:**
  - Conversion funnel drop-off identified by Performance agent
  - New channel launch requiring attribution baseline
  - Monthly business review preparation
- **Key tasks:**
  - `analyse_cohort` — cohort retention and LTV by acquisition channel
  - `diagnose_funnel` — identify conversion funnel drop-off points
  - `attribution_analysis` — first/last/multi-touch attribution for ad spend
- **Typical duration:** 1–2 weeks

### SEO/AEO Specialist (`seo_aeo`)

- **File:** `src/agents/specialists/seo_aeo.py`
- **Role:** SEO content strategy, AEO/GEO brand visibility testing and optimisation. Tests brand presence in ChatGPT and Perplexity answers.
- **Model tier:** `creative`
- **Tools:** `chatgpt` (AEO testing), `perplexity` (AEO testing), `ticket_system`, `audit_log`
- **Typical hire triggers:**
  - CMO identifies brand invisible in AI-generated answers
  - New product launch requiring SEO content strategy
  - Organic traffic decline investigation
- **Key tasks:**
  - `aeo_audit` — test brand visibility across ChatGPT and Perplexity
  - `seo_content_plan` — keyword strategy and content calendar
  - `aeo_content_brief` — content briefs optimised for AI engine visibility
- **Typical duration:** 2–4 weeks
- **Note:** AEO/GEO calls use `src/tools/llm_as_tool/chatgpt.py` and `perplexity.py` — NOT the model router. These are tool invocations checking brand presence, not agent reasoning.

### Optimizer (`optimizer`)

- **File:** `src/agents/specialists/optimizer.py`
- **Class:** `OptimizerAgent`
- **Role:** Meta-specialist that orchestrates multi-agent improvement loops. Sets a measurable quality objective, triggers a registered workflow, evaluates the output with an LLM judge (YES/NO), and either iterates or declares success and winds down. Does not produce creative or analytical output directly — it coordinates agents that do.
- **Model tier:** `strategy`
- **Tools:** `supabase_client`, `ticket_system`, `audit_log`
- **Typical hire triggers:**
  - CTR on active ad creatives drops >15% vs. 30-day moving average
  - Creative agent output quality flagged as poor by CMO review
  - New competitor creative pattern detected by Scout that warrants replication
- **Key tasks:**
  - `set_objective` — define the quality target (e.g. "replicated creatives must have predicted CTR ≥ top 20% of Creative Library")
  - `trigger_workflow` — launch `creative_optimisation` or `competitor_intelligence` workflow via `orchestrator.run_workflow()`
  - `evaluate_quality` — LLM-judge the workflow output against the objective; returns YES (success) or NO (iterate)
  - `iterate_or_complete` — if quality not met and budget remains, re-trigger specific steps; if met or budget exhausted, close ticket and wind down
- **Typical duration:** 1–2 weeks
- **Success criteria example:** "3+ replicated creatives with predicted CTR ≥ 2.5% saved to Creative Library"
- **Note:** Optimizer does not bypass governance. It is a specialist — the hiring manager proposes it, the founder approves it, and it has its own budget allocation from the specialist reserve.

### Growth Hacker (`growth_hacker`)

- **File:** `src/agents/specialists/growth_hacker.py`
- **Role:** Referral loop design, viral mechanic experiments, retention campaign strategy, D2C growth playbooks.
- **Model tier:** `creative`
- **Tools:** `shopify`, `meta_ads`, `whatsapp`, `ticket_system`, `audit_log`
- **Typical hire triggers:**
  - Retention rate below category benchmark
  - New referral/loyalty programme design needed
  - Rapid growth experiment required (new geography, new segment)
- **Key tasks:**
  - `referral_design` — referral loop mechanics and incentive structure
  - `retention_experiment` — win-back campaign design
  - `viral_mechanic` — shareable product/packaging mechanic brief
- **Typical duration:** 1–3 weeks

---

## Org Chart (AIM — example instantiation)

```
Founder
├── Portfolio CFO (holdco)
├── BD Agent (holdco)
└── AIM CEO (aim-ceo)
    ├── AIM CMO (aim-cmo)
    │   ├── AIM Creative (aim-creative)
    │   └── AIM Performance (aim-performance)
    ├── AIM Scout (aim-scout)
    ├── AIM Ops (aim-ops)
    └── AIM Finance (aim-finance)

On-demand (when active):
    AIM CEO → Data Scientist (aim-data_scientist)
    AIM CEO → Engineer (aim-engineer)
    AIM CEO → Data Analyst (aim-data_analyst)
    AIM CMO → SEO/AEO Specialist (aim-seo_aeo)
    AIM CMO → Growth Hacker (aim-growth_hacker)
    AIM CMO → Optimizer (aim-optimizer)
      └── triggers: creative_optimisation workflow
            ├── Engineer (aim-engineer)
            ├── Data Scientist (aim-data_scientist)
            └── Creative (aim-creative)
```

---

## Agent Config Schema (agent_config table)

| Column | Type | Description |
|---|---|---|
| `agent_slug` | `VARCHAR(64)` | Unique brand-scoped identifier (e.g. `aim-ceo`) |
| `agent_template` | `VARCHAR(64)` | Template class key (e.g. `ceo`, `finance`) |
| `agent_type` | `VARCHAR(32)` | `standing` or `specialist` |
| `is_specialist` | `BOOLEAN` | Explicit flag (derived from `agent_type` but queryable) |
| `model_tier` | `VARCHAR(32)` | `strategy`, `creative`, `batch`, `monitoring` |
| `heartbeat_cron` | `VARCHAR(64)` | Cron expression for scheduled runs (nullable for on-demand) |
| `monthly_budget_cap_usd` | `NUMERIC(10,4)` | Hard USD budget cap per month |
| `is_active` | `BOOLEAN` | Whether agent is active |
| `is_paused` | `BOOLEAN` | Paused via governance (can resume) |
| `reports_to_slug` | `VARCHAR(64)` | Parent agent slug in org chart |
| `config_json` | `JSONB` | Brand-specific overrides (goals, tool limits, etc.) |

---

## Key Rules for Agent Implementation

1. **Never call an LLM directly.** Always use `src.llm.provider.call(task_type, messages, ...)`.
2. **Always write audit log entries** at start and completion of every `run()` call.
3. **Always create a ticket** for every task execution, return the `ticket_id` in `AgentResult`.
4. **Check `is_paused` and `wound_down_at`** at the start of `run()` — raise `AgentPausedError` or `AgentWindDownError` as appropriate.
5. **Never access another brand's data.** Company ID scoping is enforced at the DB layer — always pass `company_id` to every query.
6. **Standing agents** use `task_type = "strategy"` or `"creative"` (never `"monitoring"` — that's heartbeat-only).
7. **Specialist agents** track `_budget_spent` and report it in `report()`.
8. **Tool access is database-driven.** `get_tools()` returns the list of permitted slugs; actual activation is checked against `tool_registry` table.
9. **Never call another agent directly.** Use `self.delegate()` for single sub-tasks or `orchestrator.run_workflow()` for multi-step pipelines. Direct instantiation bypasses audit logging and budget enforcement.
10. **Save all creative output to the Creative Library** before a task returns. Call `google_drive.save_creative()` with correct `source`, `metadata`, and `workflow_run_id`. Unsaved output cannot feed the performance feedback loop.

---

## How Agent Communication Works

Agents never import or instantiate each other directly. All inter-agent communication goes through one of two paths:

### 1. Registered Workflow (multi-step pipeline)

```python
# Inside OptimizerAgent.trigger_workflow()
from src.core import orchestrator

result = await orchestrator.run_workflow(
    workflow_name="creative_optimisation",
    company_slug=self.company_slug,
    initial_context={"objective": self.objective},
    db=db,
)
```

The orchestrator resolves each step's agent from the registry, calls `agent.run(task)`, and passes `prev_output` forward. Full run is persisted to `workflow_run` / `workflow_step` tables.

### 2. Ad-hoc Delegation (single sub-task)

```python
# Inside ScoutAgent.competitor_scan()
result = await self.delegate(
    task_subtype="rank_creatives",
    target_agent_template="data_scientist",
    context={"raw_creatives": scraped_data},
)
```

`BaseAgent.delegate()` resolves the target agent from the registry (same `company_id`), runs it, and returns the `AgentResult`. Brand isolation is always preserved — delegation across brands raises `BrandIsolationError`.

### When to use which

| Scenario | Use |
|---|---|
| Ordered pipeline where step N depends on step N-1 | `orchestrator.run_workflow()` |
| One agent needs a single answer from another | `self.delegate()` |
| Standing agent triggering a specialist | `self.delegate()` or hiring manager + governance |
| Founder asking "how are creatives doing?" | Intent router → CEO agent → `daily_performance_check` (no workflow needed) |

---

## Workflow Catalogue

Registered in `src/core/orchestrator.py` under `WORKFLOW_REGISTRY`.

### `creative_optimisation`

**Trigger:** Scout detects CTR drop >15% or creative staleness. Optimizer specialist hired by hiring manager.

| Step | Agent | Task | Output passed forward |
|---|---|---|---|
| 1 | `engineer` | `build_scraper` | Scraped competitor ad URLs + metadata |
| 2 | `data_scientist` | `rank_creatives` | Ranked list with `predicted_ctr` scores |
| 3 | `creative` | `replicate_top_ads` | Replicated ad copy + brief, saved to Creative Library |
| 4 | `optimizer` | `evaluate_quality` | YES/NO quality verdict + iteration decision |

**Success condition:** ≥3 replicated creatives with `predicted_ctr` ≥ top-20% Creative Library threshold.

**Feedback loop:** Performance agent's `update_creative_ctr` task retroactively writes `actual_ctr` to Creative Library entries after each campaign flight, improving future `rank_creatives` predictions.

---

### `competitor_intelligence`

**Trigger:** CMO requests competitive brief or Scout flags new category entrant.

| Step | Agent | Task | Output passed forward |
|---|---|---|---|
| 1 | `scout` | `competitor_scan` | Raw competitor creative + messaging data |
| 2 | `data_analyst` | `attribution_analysis` | Channel attribution breakdown for competitor spend |
| 3 | `cmo` | `campaign_brief` | Structured brief ready for Creative and Performance agents |

**Success condition:** Campaign brief created and linked to a ticket; Creative agent picks it up in next heartbeat.
