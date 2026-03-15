# SKILLS.md — BrandOS Reusable Agent Capabilities

This document catalogues the reusable skills (tool-backed capabilities) available to BrandOS agents. Each skill maps to a tool action that an agent can invoke through the tool layer.

---

## Advertising Skills

| Skill | Tool | Action | Agent(s) | Description |
|---|---|---|---|---|
| `query_meta_campaigns` | `meta_ads` | `get_campaigns` | Performance, CMO | List all Meta ad campaigns with status and budget |
| `get_meta_spend` | `meta_ads` | `get_ad_spend` | Performance, Finance | Get total Meta ad spend for a period |
| `update_meta_bid` | `meta_ads` | `update_bid` | Performance | Adjust bid for a Meta campaign |
| `search_ad_library` | `meta_ads` | `search_ad_library` | Scout | Search Meta Ad Library for competitor ads |
| `query_google_campaigns` | `google_ads` | `get_campaigns` | Performance, CMO | List Google Ads campaigns |
| `get_google_performance` | `google_ads` | `get_performance_report` | Performance | Get Google Ads performance metrics |
| `query_amazon_ads` | `amazon_ads` | `get_sponsored_products` | Performance | List Amazon sponsored product campaigns |
| `get_amazon_acos` | `amazon_ads` | `get_acos` | Performance, Finance | Get ACoS for Amazon campaigns |

## Commerce Skills

| Skill | Tool | Action | Agent(s) | Description |
|---|---|---|---|---|
| `get_shopify_orders` | `shopify` | `get_orders` | Ops, Finance | Retrieve recent Shopify orders |
| `get_shopify_inventory` | `shopify` | `get_inventory` | Ops | Check inventory levels by location |
| `get_shopify_sales` | `shopify` | `get_sales_summary` | Finance, CEO | Revenue, order count, AOV summary |
| `get_amazon_listings` | `amazon_seller` | `get_listings` | Ops | List Amazon product listings |
| `get_fba_inventory` | `amazon_seller` | `get_fba_inventory` | Ops | Check FBA inventory levels |
| `get_blinkit_orders` | `blinkit` | `get_orders` | Ops | Retrieve Blinkit quick commerce orders |
| `update_blinkit_inventory` | `blinkit` | `update_inventory` | Ops | Sync inventory to Blinkit |
| `lovable_build_page` | `lovable_shopify` | `build_page` | Creative, CMO | Generate a Shopify page via Lovable AI |

## AEO/GEO Skills (LLM-as-Tool)

| Skill | Tool | Action | Agent(s) | Description |
|---|---|---|---|---|
| `test_chatgpt_visibility` | `chatgpt_aeo` | `test_brand_visibility` | SEO/AEO | Check if brand appears in ChatGPT answers |
| `batch_chatgpt_test` | `chatgpt_aeo` | `batch_visibility_test` | SEO/AEO | Batch test brand visibility across queries |
| `test_perplexity_visibility` | `perplexity_aeo` | `test_brand_visibility` | SEO/AEO | Check brand presence in Perplexity answers |
| `batch_perplexity_test` | `perplexity_aeo` | `batch_visibility_test` | SEO/AEO | Batch test brand presence in Perplexity |

## Communication Skills

| Skill | Tool | Action | Agent(s) | Description |
|---|---|---|---|---|
| `send_email` | `gmail` | `send_email` | Ops, Finance | Send email to supplier or investor |
| `read_inbox` | `gmail` | `read_inbox` | Ops | Read recent emails |
| `send_whatsapp` | `whatsapp` | `send_message` | Ops, CEO | Send WhatsApp message to supplier/customer |
| `send_whatsapp_template` | `whatsapp` | `send_template` | Ops | Send a WhatsApp template message |

## Logistics Skills

| Skill | Tool | Action | Agent(s) | Description |
|---|---|---|---|---|
| `create_shipment` | `shiprocket` | `create_shipment` | Ops | Create a new shipment via Shiprocket |
| `track_shipment` | `shiprocket` | `track_shipment` | Ops | Track shipment status |
| `check_pincode` | `delhivery` | `check_pincode` | Ops | Check pincode serviceability |
| `track_delhivery` | `delhivery` | `track` | Ops | Track Delhivery shipment |

## Compliance Skills

| Skill | Tool | Action | Agent(s) | Description |
|---|---|---|---|---|
| `check_fssai_renewal` | `fssai` | `check_renewal_status` | Ops | Check FSSAI licence renewal status |
| `get_compliance_calendar` | `fssai` | `get_compliance_calendar` | Ops | Get upcoming compliance deadlines |

## Data Skills

| Skill | Tool | Action | Agent(s) | Description |
|---|---|---|---|---|
| `query_supabase` | `supabase_client` | `select` | All agents | Read brand/agent data from Supabase |
| `write_supabase` | `supabase_client` | `insert` | All agents | Write data to Supabase |
| `get_d2c_benchmarks` | `d2c_benchmarks` | `get_benchmarks` | Finance, CMO, Data Scientist | Get Indian D2C industry benchmarks |
| `compare_to_benchmark` | `d2c_benchmarks` | `compare_metric` | Finance, Performance | Compare a brand metric to industry median |

## Creative Library Skills

| Skill | Tool | Action | Agent(s) | Description |
|---|---|---|---|---|
| `save_creative` | `google_drive` | `save_creative` | Creative, Scout | Save creative asset to Google Drive + metadata DB |
| `get_top_creatives` | `google_drive` | `get_top_creatives` | Creative, Data Scientist | Get top-performing creatives by CTR |
| `update_actual_ctr` | `google_drive` | `update_actual_ctr` | Performance | Update actual CTR after ad flight (feedback loop) |

## Custom Integration Skills

| Skill | Tool | Action | Agent(s) | Description |
|---|---|---|---|---|
| `register_custom_api` | `custom_adapter` | (via config) | Engineer | Register a new REST API via JSON config |
| `call_custom_api` | `custom_adapter` | (dynamic) | Any | Call any registered custom API endpoint |

---

## Workflow-Triggered Skills

These skills are not invoked directly but through registered workflows in the orchestrator:

| Workflow | Skill Chain | Trigger |
|---|---|---|
| `creative_optimisation` | `build_scraper` → `rank_creatives` → `replicate_top_ads` → `evaluate_quality` | Scout flags CTR drop |
| `competitor_intelligence` | `competitor_scan` → `attribution_analysis` → `campaign_brief` | CMO requests competitive brief |

---

## Adding a New Skill

1. Implement the tool action in the relevant tool module under `src/tools/`.
2. Register the tool for the brand in `tool_registry` (database insert).
3. Add the tool slug to the agent's `get_tools()` return list.
4. Document the skill in this file.
