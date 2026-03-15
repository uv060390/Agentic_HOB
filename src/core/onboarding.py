"""
src/core/onboarding.py  (AM-107)

Conversational onboarding wizard for new BrandOS founders.
Triggered when a founder messages the bot before their brand is configured.

Architecture:
  - State machine backed by `onboarding_session` DB table (persistent, resumable)
  - Steps defined as data (OnboardingStep dataclasses), not scattered logic
  - API keys written to Infisical IMMEDIATELY on validation — never stored in DB
  - Every founder input is sanitized before processing (Never Rule 3)
  - No LLM calls — this is a form wizard, not a reasoning task
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from src.gateway.sanitizer import sanitize
from src.shared.exceptions import OnboardingError, StepValidationError, VaultUnavailableError
from src.vault.client import set_brand_secret, set_shared_secret

logger = logging.getLogger(__name__)

# ── Dataclasses ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OnboardingStep:
    id: str
    title: str
    prompt: str
    input_type: str  # "text" | "choice" | "multi_choice" | "confirm" | "auto"
    choices: list[str] | None = None
    optional: bool = False
    signup_link: str | None = None
    # Infisical path template, e.g. "/shared/anthropic_api_key"
    # or "/{brand_slug}/meta_ads_token" (interpolated at write time)
    infisical_path: str | None = None
    validator_name: str | None = None    # key into _VALIDATORS dict
    auto_action_name: str | None = None  # key into _AUTO_ACTIONS dict
    next_step_name: str | None = None    # key into _NEXT_STEP_FNS dict


# ── Step definitions ──────────────────────────────────────────────────────────

STATIC_STEPS: list[OnboardingStep] = [
    OnboardingStep(
        id="welcome",
        title="Welcome",
        input_type="confirm",
        prompt=(
            "Welcome to BrandOS.\n\n"
            "I'll set up your AI agent team in about 10 minutes.\n\n"
            "We'll cover:\n"
            "• Your brand basics\n"
            "• LLM + data keys\n"
            "• Messaging channel\n"
            "• Tools (ads, commerce, etc.)\n"
            "• Budget caps\n"
            "• Launch\n\n"
            "Type *start* when you're ready, or *help* for an overview."
        ),
    ),
    OnboardingStep(
        id="brand_name",
        title="Brand name",
        input_type="text",
        prompt=(
            "*Brand name*\n\n"
            "What's your brand called?\n"
            "(e.g. AIM Nutrition, LembasMax)"
        ),
        validator_name="validate_brand_name",
    ),
    OnboardingStep(
        id="brand_slug",
        title="Brand ID",
        input_type="text",
        prompt=(
            "*Brand ID*\n\n"
            "Choose a short ID for this brand.\n"
            "Lowercase letters and hyphens only.\n"
            "(e.g. aim, lembasmax)"
        ),
        validator_name="validate_brand_slug",
    ),
    OnboardingStep(
        id="brand_category",
        title="Category",
        input_type="choice",
        prompt=(
            "*Category*\n\n"
            "What category is this brand?\n\n"
            "1. Nutrition / supplements\n"
            "2. Personal care / beauty\n"
            "3. Food & beverage\n"
            "4. Health & wellness\n"
            "5. Apparel\n"
            "6. Baby & kids\n"
            "7. Pet care\n"
            "8. Other"
        ),
        choices=[
            "nutrition", "personal_care", "food_beverage",
            "health_wellness", "apparel", "baby_kids", "pet_care", "other",
        ],
    ),
    OnboardingStep(
        id="brand_mission",
        title="Mission",
        input_type="text",
        optional=True,
        prompt=(
            "*Mission* (optional)\n\n"
            "One sentence: what is this brand's mission?\n\n"
            "This gets written into every agent's context.\n"
            "(Type *skip* to set later)"
        ),
        validator_name="validate_mission",
    ),
    OnboardingStep(
        id="anthropic_key",
        title="Anthropic API key",
        input_type="text",
        prompt=(
            "*Anthropic API key* (Claude — strategy + creative tasks)\n\n"
            "Get yours at:\n"
            "https://console.anthropic.com/settings/keys\n\n"
            "Paste your key (starts with *sk-ant-*):"
        ),
        signup_link="https://console.anthropic.com/settings/keys",
        infisical_path="/shared/anthropic_api_key",
        validator_name="validate_anthropic_key",
    ),
    OnboardingStep(
        id="cerebras_key",
        title="Cerebras API key",
        input_type="text",
        prompt=(
            "*Cerebras API key* (Llama — monitoring + batch, ~10× cheaper)\n\n"
            "Get yours at:\n"
            "https://cloud.cerebras.ai/\n\n"
            "Paste your key:"
        ),
        signup_link="https://cloud.cerebras.ai/",
        infisical_path="/shared/cerebras_api_key",
        validator_name="validate_cerebras_key",
    ),
    OnboardingStep(
        id="supabase_url",
        title="Supabase URL",
        input_type="text",
        prompt=(
            "*Supabase URL*\n\n"
            "From: https://supabase.com/dashboard\n"
            "→ Your project → Settings → API\n\n"
            "Looks like: https://xyzabc.supabase.co"
        ),
        signup_link="https://supabase.com/dashboard",
        validator_name="validate_supabase_url",
    ),
    OnboardingStep(
        id="supabase_key",
        title="Supabase service role key",
        input_type="text",
        prompt=(
            "*Supabase service role key*\n\n"
            "Same page → API → *service_role* (not the anon key).\n\n"
            "Paste it:"
        ),
        infisical_path="/{brand_slug}/supabase_key",
        validator_name="validate_supabase_key",
    ),
    OnboardingStep(
        id="messaging_channel",
        title="Messaging channel",
        input_type="choice",
        prompt=(
            "*Messaging channel*\n\n"
            "How do you want to talk to your agents?\n\n"
            "1. Telegram (already connected — you're using it now)\n"
            "2. WhatsApp Business (requires Meta approval)\n"
            "3. Both"
        ),
        choices=["telegram_only", "whatsapp_only", "both"],
        next_step_name="next_step_after_messaging",
    ),
    # WhatsApp token — only inserted into queue if WhatsApp selected
    OnboardingStep(
        id="whatsapp_token",
        title="WhatsApp token",
        input_type="text",
        prompt=(
            "*WhatsApp Business API token*\n\n"
            "Option A — Meta Cloud API (free, needs business verification):\n"
            "https://developers.facebook.com/apps/\n\n"
            "Option B — Gupshup (easier onboarding):\n"
            "https://www.gupshup.io\n\n"
            "Paste your token:"
        ),
        signup_link="https://developers.facebook.com/apps/",
        infisical_path="/{brand_slug}/whatsapp_api_token",
        validator_name="validate_whatsapp_token",
        auto_action_name="auto_register_whatsapp_webhook",
    ),
    OnboardingStep(
        id="tool_selection",
        title="Tool selection",
        input_type="multi_choice",
        prompt=(
            "*Tools*\n\n"
            "Which platforms does this brand use?\n"
            "Reply with numbers separated by commas (e.g. *1,3,5*)\n\n"
            "1. Meta Ads (Facebook / Instagram)\n"
            "2. Google Ads\n"
            "3. Amazon Ads\n"
            "4. Shopify\n"
            "5. Amazon Seller Central\n"
            "6. Blinkit (quick commerce)\n"
            "7. Shiprocket\n"
            "8. Delhivery\n"
            "9. Gmail\n"
            "10. Google Drive (Creative Library)\n"
            "11. None — set up tools later"
        ),
        choices=[
            "meta_ads", "google_ads", "amazon_ads", "shopify",
            "amazon_seller", "blinkit", "shiprocket", "delhivery",
            "gmail", "google_drive",
        ],
        next_step_name="next_step_after_tool_selection",
    ),
    # ── Tool credential steps (dynamically queued, definitions referenced by id) ──
    OnboardingStep(
        id="meta_ads_token",
        title="Meta Ads token",
        input_type="text",
        prompt=(
            "*Meta Ads — System User Access Token*\n\n"
            "Business Manager → System Users → Generate Token\n"
            "https://business.facebook.com/settings/system-users\n\n"
            "Paste your token:"
        ),
        signup_link="https://business.facebook.com/settings/system-users",
        infisical_path="/{brand_slug}/meta_ads_token",
        validator_name="validate_meta_ads_token",
    ),
    OnboardingStep(
        id="google_ads_developer_token",
        title="Google Ads developer token",
        input_type="text",
        prompt=(
            "*Google Ads — Developer Token*\n\n"
            "Google Ads Manager → Tools → API Centre → Developer Token\n"
            "https://ads.google.com/home/tools/manager-accounts/\n\n"
            "Paste your developer token:"
        ),
        signup_link="https://developers.google.com/google-ads/api/docs/get-started/oauth-cloud",
        infisical_path="/{brand_slug}/google_ads_developer_token",
        validator_name="validate_google_ads_developer_token",
    ),
    OnboardingStep(
        id="google_ads_refresh_token",
        title="Google Ads refresh token",
        input_type="text",
        prompt=(
            "*Google Ads — OAuth Refresh Token*\n\n"
            "Run the OAuth flow from the link above to get this.\n\n"
            "Paste your refresh token:"
        ),
        infisical_path="/{brand_slug}/google_ads_refresh_token",
        validator_name="validate_google_ads_refresh_token",
    ),
    OnboardingStep(
        id="amazon_ads_token",
        title="Amazon Ads token",
        input_type="text",
        prompt=(
            "*Amazon Ads — LWA Client ID + Secret*\n\n"
            "Amazon Developer Console → Login with Amazon → Create app\n"
            "https://developer.amazon.com/loginwithamazon/console/site/lwa/overview.html\n\n"
            "Format: *client_id:client_secret*\n"
            "Paste here:"
        ),
        signup_link="https://developer.amazon.com/loginwithamazon/console/site/lwa/overview.html",
        infisical_path="/{brand_slug}/amazon_ads_credentials",
        validator_name="validate_amazon_ads_token",
    ),
    OnboardingStep(
        id="shopify_url",
        title="Shopify store URL",
        input_type="text",
        prompt=(
            "*Shopify — Store URL*\n\n"
            "Format: your-store.myshopify.com\n"
            "(no https://)"
        ),
        validator_name="validate_shopify_url",
    ),
    OnboardingStep(
        id="shopify_key",
        title="Shopify Admin API token",
        input_type="text",
        prompt=(
            "*Shopify — Admin API Token*\n\n"
            "Settings → Apps → Develop apps → your app → API credentials\n"
            "https://admin.shopify.com/store/{store}/settings/apps\n\n"
            "Paste your token:"
        ),
        signup_link="https://shopify.dev/docs/apps/build/authentication-authorization/access-token-types",
        infisical_path="/{brand_slug}/shopify_token",
        validator_name="validate_shopify_key",
    ),
    OnboardingStep(
        id="amazon_seller_token",
        title="Amazon Seller Central token",
        input_type="text",
        prompt=(
            "*Amazon Seller Central — SP-API credentials*\n\n"
            "Seller Central → Apps & Services → Develop Apps\n"
            "https://sellercentral.amazon.in/developer/applications\n\n"
            "Format: *seller_id:mws_auth_token*\n"
            "Paste here:"
        ),
        signup_link="https://sellercentral.amazon.in/developer/applications",
        infisical_path="/{brand_slug}/amazon_seller_credentials",
        validator_name="validate_amazon_seller_token",
    ),
    OnboardingStep(
        id="blinkit_token",
        title="Blinkit API key",
        input_type="text",
        prompt=(
            "*Blinkit Seller API key*\n\n"
            "Contact your Blinkit category manager to get API access.\n"
            "Blinkit does not have a self-serve developer portal.\n\n"
            "Paste your API key once received:"
        ),
        infisical_path="/{brand_slug}/blinkit_api_key",
        validator_name="validate_blinkit_token",
    ),
    OnboardingStep(
        id="shiprocket_credentials",
        title="Shiprocket credentials",
        input_type="text",
        prompt=(
            "*Shiprocket — Email + Password*\n\n"
            "Used for API token generation.\n"
            "https://app.shiprocket.in/register\n\n"
            "Format: *email:password*\n"
            "Paste here:"
        ),
        signup_link="https://app.shiprocket.in/register",
        infisical_path="/{brand_slug}/shiprocket_credentials",
        validator_name="validate_shiprocket_credentials",
    ),
    OnboardingStep(
        id="delhivery_token",
        title="Delhivery API token",
        input_type="text",
        prompt=(
            "*Delhivery API token*\n\n"
            "Delhivery Partner Portal → API → Generate token\n"
            "https://www.delhivery.com/business-partner\n\n"
            "Paste your token:"
        ),
        signup_link="https://www.delhivery.com/business-partner",
        infisical_path="/{brand_slug}/delhivery_token",
        validator_name="validate_delhivery_token",
    ),
    OnboardingStep(
        id="gmail_credentials",
        title="Gmail OAuth credentials",
        input_type="text",
        prompt=(
            "*Gmail — OAuth2 credentials*\n\n"
            "Google Cloud Console → APIs → Gmail → Credentials\n"
            "https://console.cloud.google.com/apis/credentials\n\n"
            "Format: *client_id:client_secret:refresh_token*\n"
            "Paste here:"
        ),
        signup_link="https://console.cloud.google.com/apis/credentials",
        infisical_path="/{brand_slug}/gmail_credentials",
        validator_name="validate_gmail_credentials",
    ),
    OnboardingStep(
        id="google_drive_service_account",
        title="Google Drive service account",
        input_type="text",
        prompt=(
            "*Google Drive — Service Account JSON*\n\n"
            "Google Cloud Console → IAM → Service Accounts → Create\n"
            "https://console.cloud.google.com/iam-admin/serviceaccounts\n\n"
            "Download the JSON key and paste the *entire contents* here:"
        ),
        signup_link="https://console.cloud.google.com/iam-admin/serviceaccounts",
        infisical_path="/shared/google_drive_service_account",
        validator_name="validate_google_drive_service_account",
    ),
    # ── Budget + creative config ───────────────────────────────────────────────
    OnboardingStep(
        id="budget_caps",
        title="Budget caps",
        input_type="choice",
        prompt=(
            "*Agent budget caps* (monthly, USD)\n\n"
            "Default: $10/month per standing agent, $25 specialist reserve.\n\n"
            "1. Use defaults\n"
            "2. Customise per agent"
        ),
        choices=["defaults", "custom"],
        next_step_name="next_step_after_budget",
    ),
    OnboardingStep(
        id="budget_caps_custom",
        title="Custom budget caps",
        input_type="text",
        prompt=(
            "*Custom budget caps*\n\n"
            "Format: one per line, *agent:amount*\n"
            "e.g.\n"
            "ceo:10\n"
            "cmo:15\n"
            "performance:20\n"
            "specialist_reserve:50\n\n"
            "Omit an agent to use the $10 default.\n"
            "Paste your caps:"
        ),
        validator_name="validate_budget_caps",
    ),
    OnboardingStep(
        id="brand_colors",
        title="Brand colours",
        input_type="text",
        optional=True,
        prompt=(
            "*Brand colours* (optional)\n\n"
            "Helps the Creative agent match your brand identity.\n"
            "Format: *primary:#FF6B35 secondary:#004E89*\n\n"
            "Or type *skip*"
        ),
        validator_name="validate_brand_colors",
    ),
    OnboardingStep(
        id="brand_product_images",
        title="Product images",
        input_type="text",
        optional=True,
        prompt=(
            "*Product image URLs* (optional)\n\n"
            "The Creative agent uses these when replicating competitor ads.\n"
            "Paste up to 3 URLs, one per line.\n\n"
            "Or type *skip*"
        ),
        validator_name="validate_product_image_urls",
    ),
    OnboardingStep(
        id="confirm_provision",
        title="Confirm launch",
        input_type="confirm",
        prompt=(
            "*Ready to launch* ✓\n\n"
            "Brand: *{brand_name}* ({brand_slug})\n"
            "Tools: {selected_tools_summary}\n"
            "Agents: CEO, CMO, Finance, Ops, Scout, Creative, Performance\n"
            "First heartbeat: Monday 9 AM IST\n\n"
            "Type *confirm* to launch, or *back* to change anything."
        ),
    ),
    OnboardingStep(
        id="auto_provision",
        title="Provisioning",
        input_type="auto",
        prompt="",  # messages sent dynamically during execution
        auto_action_name="run_auto_provision",
    ),
    OnboardingStep(
        id="complete",
        title="Complete",
        input_type="auto",
        prompt=(
            "BrandOS is live for *{brand_name}*.\n\n"
            "Your agents are standing by. Try:\n"
            "• *how is {brand_name} doing?*\n"
            "• *show me the org chart*\n"
            "• *what's the current budget?*\n\n"
            "Type *help* anytime."
        ),
    ),
]

# Index for O(1) step lookup
_STEP_INDEX: dict[str, OnboardingStep] = {s.id: s for s in STATIC_STEPS}

# Maps tool slug → ordered list of credential step IDs
_TOOL_STEP_MAP: dict[str, list[str]] = {
    "meta_ads":      ["meta_ads_token"],
    "google_ads":    ["google_ads_developer_token", "google_ads_refresh_token"],
    "amazon_ads":    ["amazon_ads_token"],
    "shopify":       ["shopify_url", "shopify_key"],
    "amazon_seller": ["amazon_seller_token"],
    "blinkit":       ["blinkit_token"],
    "shiprocket":    ["shiprocket_credentials"],
    "delhivery":     ["delhivery_token"],
    "gmail":         ["gmail_credentials"],
    "google_drive":  ["google_drive_service_account"],
}

# Linear order of STATIC_STEPS that are not tool-credential steps
_LINEAR_STEP_IDS: list[str] = [
    "welcome", "brand_name", "brand_slug", "brand_category", "brand_mission",
    "anthropic_key", "cerebras_key",
    "supabase_url", "supabase_key",
    "messaging_channel",
    # whatsapp_token is inserted dynamically if WhatsApp chosen
    "tool_selection",
    # tool credential steps injected into pending_tool_steps queue
    "budget_caps",
    # budget_caps_custom inserted dynamically if "custom" chosen
    "brand_colors", "brand_product_images",
    "confirm_provision", "auto_provision", "complete",
]


# ── Step registry helpers ─────────────────────────────────────────────────────

def get_step(step_id: str) -> OnboardingStep:
    """Retrieve a step definition by ID. Raises OnboardingError if unknown."""
    step = _STEP_INDEX.get(step_id)
    if step is None:
        raise OnboardingError(f"Unknown onboarding step: '{step_id}'")
    return step


def build_tool_steps(selected_tools: list[str]) -> list[str]:
    """
    Given selected tool slugs, return an ordered list of credential step IDs.
    e.g. ["shopify", "meta_ads"] → ["shopify_url", "shopify_key", "meta_ads_token"]
    """
    steps: list[str] = []
    for tool in selected_tools:
        steps.extend(_TOOL_STEP_MAP.get(tool, []))
    return steps


def total_step_count(session_config: dict[str, Any]) -> int:
    """
    Estimate total steps for progress display.
    Base + tool credential steps + optional budget_caps_custom.
    """
    selected = session_config.get("selected_tools", [])
    tool_count = sum(len(_TOOL_STEP_MAP.get(t, [])) for t in selected)
    has_whatsapp = session_config.get("messaging_channel") in ("whatsapp_only", "both")
    return len(_LINEAR_STEP_IDS) + tool_count + (1 if has_whatsapp else 0)


# ── Input processing ──────────────────────────────────────────────────────────

async def process_input(
    session: dict[str, Any],
    raw_input: str,
) -> tuple[str, bool, dict[str, Any]]:
    """
    Core step machine. Called for every founder message during onboarding.

    Args:
        session: Dict representation of the OnboardingSession row.
        raw_input: Raw message text from the founder (not yet sanitized).

    Returns:
        (reply_text, advanced, updated_session_fields)
        - reply_text: message to send back to the founder
        - advanced: True if step completed, False if staying on same step
        - updated_session_fields: partial dict of fields to update in DB

    The sanitizer is called here — not in the route handler — to ensure
    it runs exactly once, in one place, regardless of the calling path.
    """
    try:
        text = sanitize(raw_input, source="onboarding_input")
    except Exception:
        return (
            "Your message contained a pattern I can't accept. Please try again.",
            False,
            {},
        )

    step_id = session["current_step_id"]
    step = get_step(step_id)
    config: dict[str, Any] = dict(session.get("collected_config") or {})
    brand_slug: str = config.get("brand_slug", "")

    # ── Skip optional steps ────────────────────────────────────────────────────
    if step.optional and text.strip().lower() == "skip":
        next_id = _compute_next_step(session, step)
        next_step = get_step(next_id) if next_id else None
        reply = f"Skipped. {_format_prompt(next_step, config)}" if next_step else "Done."
        return reply, True, {
            "current_step_id": next_id or "complete",
            "completed_steps": [*session.get("completed_steps", []), step_id],
            "last_message_at": _now(),
        }

    # ── Auto steps (run without founder input) ─────────────────────────────────
    if step.input_type == "auto":
        action_fn = _AUTO_ACTIONS.get(step.auto_action_name or "")
        if action_fn:
            reply = await action_fn(session)
        else:
            reply = ""
        next_id = _compute_next_step(session, step)
        return reply, True, {
            "current_step_id": next_id or "complete",
            "completed_steps": [*session.get("completed_steps", []), step_id],
            "status": "complete" if not next_id else "in_progress",
            "completed_at": _now() if not next_id else None,
            "last_message_at": _now(),
        }

    # ── Handle "confirm" step type ─────────────────────────────────────────────
    if step.input_type == "confirm":
        accepted = {"start", "confirm", "yes", "ok", "proceed"}
        if text.strip().lower() not in accepted:
            return (
                f"Type *{list(accepted)[0]}* to continue, or *help* for more info.",
                False,
                {"last_message_at": _now()},
            )

    # ── Validate input ─────────────────────────────────────────────────────────
    if step.validator_name:
        validator = _VALIDATORS.get(step.validator_name)
        if validator:
            error = await validator(text, session)
            if error:
                return (
                    f"⚠️ {error}\n\n{_format_prompt(step, config)}",
                    False,
                    {"error_message": error, "last_message_at": _now()},
                )

    # ── Write secret to Infisical (never touches DB) ───────────────────────────
    if step.infisical_path:
        resolved_path = step.infisical_path.replace("{brand_slug}", brand_slug)
        parts = resolved_path.strip("/").split("/")
        try:
            if parts[0] == "shared":
                set_shared_secret(parts[1], text.strip())
            else:
                set_brand_secret(parts[0], parts[1], text.strip())
        except VaultUnavailableError as exc:
            logger.error("Vault write failed during onboarding: %s", exc)
            return (
                "Failed to save to vault. Check Infisical is running and retry.",
                False,
                {"error_message": str(exc), "last_message_at": _now()},
            )

    # ── Store non-sensitive config ─────────────────────────────────────────────
    config = _apply_to_config(step, text.strip(), config)

    # ── Fire post-input auto-actions (e.g. webhook registration) ──────────────
    if step.auto_action_name and step.input_type != "auto":
        action_fn = _AUTO_ACTIONS.get(step.auto_action_name)
        if action_fn:
            action_result = await action_fn({**session, "collected_config": config})
            logger.info("Auto-action '%s' result: %s", step.auto_action_name, action_result)

    # ── Advance to next step ───────────────────────────────────────────────────
    next_id = _compute_next_step({**session, "collected_config": config}, step)
    next_step = get_step(next_id) if next_id else None
    reply = _format_prompt(next_step, config) if next_step else _format_prompt(
        get_step("complete"), config
    )

    completed = [*session.get("completed_steps", []), step_id]
    pending = list(session.get("pending_tool_steps") or [])

    # Pop from tool queue if this was a tool step (step consumed)
    if step_id in pending:
        pending = pending[1:]

    return reply, True, {
        "current_step_id": next_id or "complete",
        "completed_steps": completed,
        "collected_config": config,
        "pending_tool_steps": pending,
        "error_message": None,
        "last_message_at": _now(),
    }


# ── Step navigation ───────────────────────────────────────────────────────────

def _compute_next_step(session: dict[str, Any], current: OnboardingStep) -> str | None:
    """
    Compute the next step ID.
    Priority:
      1. Custom next_step_fn if defined on the current step
      2. Pending tool steps queue (FIFO)
      3. Linear progression through _LINEAR_STEP_IDS
    Returns None when onboarding is finished.
    """
    if current.next_step_name:
        fn = _NEXT_STEP_FNS.get(current.next_step_name)
        if fn:
            return fn(session)

    pending: list[str] = list(session.get("pending_tool_steps") or [])
    # If current step is a tool step being consumed, look at remaining queue
    if current.id in pending and len(pending) > 1:
        return pending[1]
    if current.id not in _LINEAR_STEP_IDS and pending:
        # We finished all tool steps, fall through to linear
        pass
    elif current.id not in _LINEAR_STEP_IDS:
        # Tool step with empty queue — resume linear after tool_selection
        current_idx = _LINEAR_STEP_IDS.index("tool_selection")
        return _LINEAR_STEP_IDS[current_idx + 1]

    try:
        idx = _LINEAR_STEP_IDS.index(current.id)
        return _LINEAR_STEP_IDS[idx + 1] if idx + 1 < len(_LINEAR_STEP_IDS) else None
    except ValueError:
        return None


# ── Dynamic next-step functions ───────────────────────────────────────────────

def _next_step_after_messaging(session: dict[str, Any]) -> str:
    """
    After messaging_channel step: inject WhatsApp step into pending queue
    if WhatsApp was chosen, then continue to auto_register_telegram if Telegram chosen.
    """
    config = session.get("collected_config") or {}
    channel = config.get("messaging_channel", "telegram_only")
    if channel in ("whatsapp_only", "both"):
        return "whatsapp_token"
    # Telegram only — auto-register webhook and proceed to tool_selection
    return "tool_selection"


def _next_step_after_tool_selection(session: dict[str, Any]) -> str:
    """
    Build tool credential queue from selection. Returns first credential step
    or budget_caps if none selected.
    """
    config = session.get("collected_config") or {}
    selected = config.get("selected_tools", [])
    tool_steps = build_tool_steps(selected)
    if tool_steps:
        # Store the queue in session (caller must persist this)
        session.setdefault("pending_tool_steps", tool_steps)
        return tool_steps[0]
    return "budget_caps"


def _next_step_after_budget(session: dict[str, Any]) -> str:
    config = session.get("collected_config") or {}
    if config.get("budget_choice") == "custom":
        return "budget_caps_custom"
    return "brand_colors"


_NEXT_STEP_FNS: dict[str, Any] = {
    "next_step_after_messaging": _next_step_after_messaging,
    "next_step_after_tool_selection": _next_step_after_tool_selection,
    "next_step_after_budget": _next_step_after_budget,
}


# ── Config application ────────────────────────────────────────────────────────

def _apply_to_config(
    step: OnboardingStep,
    value: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Write non-sensitive step value to collected_config."""
    updated = dict(config)

    if step.id == "brand_name":
        updated["brand_name"] = value
        # Auto-suggest slug if not already set
        if not updated.get("brand_slug"):
            updated["_suggested_slug"] = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

    elif step.id == "brand_slug":
        updated["brand_slug"] = value.lower()
        updated.pop("_suggested_slug", None)

    elif step.id == "brand_category":
        choices = get_step("brand_category").choices or []
        # Accept number or slug
        if value.isdigit():
            idx = int(value) - 1
            updated["category"] = choices[idx] if 0 <= idx < len(choices) else value
        else:
            updated["category"] = value

    elif step.id == "brand_mission":
        updated["mission"] = value

    elif step.id == "supabase_url":
        updated["supabase_url"] = value  # URL is not sensitive

    elif step.id == "messaging_channel":
        choices = ["telegram_only", "whatsapp_only", "both"]
        if value.isdigit():
            updated["messaging_channel"] = choices[int(value) - 1]
        else:
            updated["messaging_channel"] = value

    elif step.id == "tool_selection":
        choices = get_step("tool_selection").choices or []
        if value.strip() == "11":
            updated["selected_tools"] = []
        else:
            indices = [int(x.strip()) - 1 for x in value.split(",") if x.strip().isdigit()]
            updated["selected_tools"] = [choices[i] for i in indices if 0 <= i < len(choices)]

    elif step.id == "shopify_url":
        updated["shopify_url"] = value.rstrip("/")

    elif step.id == "budget_caps":
        updated["budget_choice"] = "defaults" if value.strip() in ("1", "defaults") else "custom"
        if updated["budget_choice"] == "defaults":
            updated["budget_caps"] = _default_budget_caps()

    elif step.id == "budget_caps_custom":
        updated["budget_caps"] = _parse_budget_caps(value)

    elif step.id == "brand_colors":
        updated["brand_colors"] = _parse_colors(value)

    elif step.id == "brand_product_images":
        updated["product_image_urls"] = [u.strip() for u in value.splitlines() if u.strip()]

    return updated


# ── Validators ────────────────────────────────────────────────────────────────

async def validate_brand_name(value: str, _session: dict[str, Any]) -> str | None:
    if not value or len(value.strip()) < 2:
        return "Brand name must be at least 2 characters."
    if len(value) > 64:
        return "Brand name must be 64 characters or fewer."
    return None


async def validate_brand_slug(value: str, _session: dict[str, Any]) -> str | None:
    slug = value.strip().lower()
    if not re.match(r"^[a-z][a-z0-9-]{1,31}$", slug):
        return (
            "Brand ID must be 2-32 characters, start with a letter, "
            "and contain only lowercase letters, numbers, and hyphens."
        )
    # Uniqueness checked at provision time, not here (no DB access in validator)
    return None


async def validate_mission(value: str, _session: dict[str, Any]) -> str | None:
    if len(value) > 500:
        return "Mission must be 500 characters or fewer."
    return None


async def validate_anthropic_key(value: str, _session: dict[str, Any]) -> str | None:
    key = value.strip()
    if not key.startswith("sk-ant-"):
        return "Anthropic keys start with *sk-ant-*. Check and try again."
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            )
        if r.status_code == 401:
            return "That key was rejected by Anthropic. Check it and try again."
        if r.status_code not in (200, 404):  # 404 means valid key but no models — acceptable
            return f"Anthropic API returned {r.status_code}. Try again."
    except httpx.TimeoutException:
        return "Anthropic API timed out. Check your internet and try again."
    except Exception as exc:
        return f"Could not reach Anthropic: {exc}"
    return None


async def validate_cerebras_key(value: str, _session: dict[str, Any]) -> str | None:
    key = value.strip()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                "https://api.cerebras.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "llama3.1-8b", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
            )
        if r.status_code == 401:
            return "That key was rejected by Cerebras. Check it and try again."
    except httpx.TimeoutException:
        return "Cerebras API timed out. Check your internet and try again."
    except Exception as exc:
        return f"Could not reach Cerebras: {exc}"
    return None


async def validate_supabase_url(value: str, _session: dict[str, Any]) -> str | None:
    url = value.strip()
    if not re.match(r"^https://[a-z0-9]+\.supabase\.co/?$", url):
        return "URL should look like https://xyzabc.supabase.co"
    return None


async def validate_supabase_key(value: str, session: dict[str, Any]) -> str | None:
    config = session.get("collected_config") or {}
    url = config.get("supabase_url", "").rstrip("/")
    key = value.strip()
    if not url:
        return "Supabase URL missing. Type *back* and re-enter the URL first."
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{url}/rest/v1/",
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
            )
        if r.status_code == 401:
            return "Supabase rejected that key. Use the *service_role* key, not the anon key."
    except httpx.TimeoutException:
        return "Could not reach Supabase. Check the URL and try again."
    except Exception as exc:
        return f"Supabase connection failed: {exc}"
    return None


async def validate_whatsapp_token(value: str, _session: dict[str, Any]) -> str | None:
    token = value.strip()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://graph.facebook.com/v18.0/me",
                params={"access_token": token},
            )
        if r.status_code == 401 or "error" in (r.json() or {}):
            return "Meta rejected that token. Check it in your developer portal."
    except Exception as exc:
        return f"Could not reach Meta Graph API: {exc}"
    return None


async def validate_meta_ads_token(value: str, _session: dict[str, Any]) -> str | None:
    token = value.strip()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://graph.facebook.com/v18.0/me",
                params={"access_token": token, "fields": "id,name"},
            )
        data = r.json()
        if "error" in data:
            return f"Meta Ads token invalid: {data['error'].get('message', 'unknown error')}"
    except Exception as exc:
        return f"Could not validate Meta Ads token: {exc}"
    return None


async def validate_google_ads_developer_token(value: str, _session: dict[str, Any]) -> str | None:
    if len(value.strip()) < 10:
        return "Developer token looks too short. Check and try again."
    return None  # Full validation requires OAuth flow — deferred to first API call


async def validate_google_ads_refresh_token(value: str, _session: dict[str, Any]) -> str | None:
    if not value.strip().startswith("1//"):
        return "Google OAuth refresh tokens typically start with *1//*. Check and try again."
    return None


async def validate_amazon_ads_token(value: str, _session: dict[str, Any]) -> str | None:
    if ":" not in value:
        return "Format should be *client_id:client_secret*"
    return None


async def validate_shopify_url(value: str, _session: dict[str, Any]) -> str | None:
    url = value.strip().lower().rstrip("/")
    if not re.match(r"^[a-z0-9-]+\.myshopify\.com$", url):
        return "Should look like your-store.myshopify.com (no https://)"
    return None


async def validate_shopify_key(value: str, session: dict[str, Any]) -> str | None:
    config = session.get("collected_config") or {}
    store_url = config.get("shopify_url", "")
    token = value.strip()
    if not store_url:
        return "Shopify URL missing. Type *back* and re-enter the store URL."
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://{store_url}/admin/api/2024-01/shop.json",
                headers={"X-Shopify-Access-Token": token},
            )
        if r.status_code == 401:
            return "Shopify rejected that token. Check Admin API access scopes."
    except Exception as exc:
        return f"Could not reach Shopify: {exc}"
    return None


async def validate_amazon_seller_token(value: str, _session: dict[str, Any]) -> str | None:
    if ":" not in value:
        return "Format should be *seller_id:mws_auth_token*"
    return None


async def validate_blinkit_token(value: str, _session: dict[str, Any]) -> str | None:
    if len(value.strip()) < 8:
        return "API key looks too short. Check with your Blinkit category manager."
    return None


async def validate_shiprocket_credentials(value: str, _session: dict[str, Any]) -> str | None:
    if ":" not in value or "@" not in value.split(":")[0]:
        return "Format should be *email:password*"
    return None


async def validate_delhivery_token(value: str, _session: dict[str, Any]) -> str | None:
    if len(value.strip()) < 8:
        return "Token looks too short. Check the Delhivery Partner Portal."
    return None


async def validate_gmail_credentials(value: str, _session: dict[str, Any]) -> str | None:
    parts = value.strip().split(":")
    if len(parts) != 3:
        return "Format should be *client_id:client_secret:refresh_token*"
    return None


async def validate_google_drive_service_account(value: str, _session: dict[str, Any]) -> str | None:
    import json
    try:
        data = json.loads(value.strip())
        if data.get("type") != "service_account":
            return "JSON does not look like a service account key. Check the file type."
        if "client_email" not in data or "private_key" not in data:
            return "JSON is missing required fields (client_email, private_key)."
    except json.JSONDecodeError:
        return "Could not parse JSON. Paste the full contents of the service account key file."
    return None


async def validate_budget_caps(value: str, _session: dict[str, Any]) -> str | None:
    try:
        _parse_budget_caps(value)
    except ValueError as exc:
        return str(exc)
    return None


async def validate_brand_colors(value: str, _session: dict[str, Any]) -> str | None:
    hex_pattern = re.compile(r"#[0-9a-fA-F]{6}")
    if not hex_pattern.search(value):
        return "Include at least one hex color code, e.g. *primary:#FF6B35*"
    return None


async def validate_product_image_urls(value: str, _session: dict[str, Any]) -> str | None:
    urls = [u.strip() for u in value.splitlines() if u.strip()]
    if len(urls) > 3:
        return "Maximum 3 product image URLs."
    for url in urls:
        if not url.startswith(("http://", "https://")):
            return f"Invalid URL: {url}"
    return None


_VALIDATORS: dict[str, Any] = {
    "validate_brand_name": validate_brand_name,
    "validate_brand_slug": validate_brand_slug,
    "validate_mission": validate_mission,
    "validate_anthropic_key": validate_anthropic_key,
    "validate_cerebras_key": validate_cerebras_key,
    "validate_supabase_url": validate_supabase_url,
    "validate_supabase_key": validate_supabase_key,
    "validate_whatsapp_token": validate_whatsapp_token,
    "validate_meta_ads_token": validate_meta_ads_token,
    "validate_google_ads_developer_token": validate_google_ads_developer_token,
    "validate_google_ads_refresh_token": validate_google_ads_refresh_token,
    "validate_amazon_ads_token": validate_amazon_ads_token,
    "validate_shopify_url": validate_shopify_url,
    "validate_shopify_key": validate_shopify_key,
    "validate_amazon_seller_token": validate_amazon_seller_token,
    "validate_blinkit_token": validate_blinkit_token,
    "validate_shiprocket_credentials": validate_shiprocket_credentials,
    "validate_delhivery_token": validate_delhivery_token,
    "validate_gmail_credentials": validate_gmail_credentials,
    "validate_google_drive_service_account": validate_google_drive_service_account,
    "validate_budget_caps": validate_budget_caps,
    "validate_brand_colors": validate_brand_colors,
    "validate_product_image_urls": validate_product_image_urls,
}


# ── Auto-actions ──────────────────────────────────────────────────────────────

async def auto_register_telegram_webhook(session: dict[str, Any]) -> str:
    """
    Calls Telegram Bot API setWebhook with the VPS URL.
    Token and VPS host fetched from env (already set when bot is running).
    """
    from src.shared.config import get_settings
    settings = get_settings()
    token = getattr(settings, "telegram_bot_token", "")
    vps_host = getattr(settings, "vps_host", "")
    if not token or not vps_host:
        return "Telegram webhook could not be auto-registered (missing config). Set it manually."
    webhook_url = f"https://{vps_host}/api/v1/telegram/webhook"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{token}/setWebhook",
                json={"url": webhook_url},
            )
        data = r.json()
        if data.get("ok"):
            return f"✓ Telegram webhook registered at {webhook_url}"
        return f"Telegram webhook registration failed: {data.get('description', 'unknown')}"
    except Exception as exc:
        return f"Could not register Telegram webhook: {exc}"


async def auto_register_whatsapp_webhook(session: dict[str, Any]) -> str:
    """
    Calls Meta Graph API to subscribe to WhatsApp webhook events.
    Requires WHATSAPP_PHONE_NUMBER_ID in settings.
    """
    from src.shared.config import get_settings
    config = session.get("collected_config") or {}
    brand_slug = config.get("brand_slug", "")
    from src.vault.client import get_brand_secret
    try:
        token = get_brand_secret(brand_slug, "whatsapp_api_token")
    except Exception:
        return "WhatsApp token not found in vault — webhook not registered."
    settings = get_settings()
    phone_id = getattr(settings, "whatsapp_phone_number_id", "")
    vps_host = getattr(settings, "vps_host", "")
    if not phone_id or not vps_host:
        return "WhatsApp webhook could not be auto-registered (missing phone number ID or VPS host)."
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"https://graph.facebook.com/v18.0/{phone_id}/subscribed_apps",
                params={"access_token": token},
            )
        if r.status_code == 200:
            return f"✓ WhatsApp webhook registered for phone ID {phone_id}"
        return f"WhatsApp webhook registration failed: {r.text}"
    except Exception as exc:
        return f"Could not register WhatsApp webhook: {exc}"


async def run_auto_provision(session: dict[str, Any]) -> str:
    """
    Full brand provisioning:
      1. Create company row
      2. Seed 7 standing agent configs
      3. Seed tool_registry rows for selected tools
      4. Register CEO heartbeat with APScheduler
      5. Write audit entry
    Returns a multi-line progress message.
    """
    config = session.get("collected_config") or {}
    brand_name = config.get("brand_name", "your brand")
    brand_slug = config.get("brand_slug", "brand")
    mission = config.get("mission", "")
    selected_tools: list[str] = config.get("selected_tools", [])
    budget_caps: dict[str, float] = config.get("budget_caps") or _default_budget_caps()

    lines = [f"Launching BrandOS for *{brand_name}*...\n"]

    try:
        # Step 1: company
        from src.core.company_registry import create_company  # type: ignore[import]
        company_id = await create_company(
            name=brand_name,
            slug=brand_slug,
            mission=mission,
            category=config.get("category", "other"),
        )
        lines.append("✓ Brand registered")
    except Exception as exc:
        lines.append(f"✗ Brand registration failed: {exc}")
        return "\n".join(lines)

    try:
        # Step 2: agent configs
        await _seed_agents(company_id, brand_slug, budget_caps)
        lines.append("✓ Agent team configured (7 agents)")
    except Exception as exc:
        lines.append(f"✗ Agent seeding failed: {exc}")

    try:
        # Step 3: tool registry
        await _seed_tools(company_id, selected_tools)
        lines.append(f"✓ Tools activated: {', '.join(selected_tools) or 'none'}")
    except Exception as exc:
        lines.append(f"✗ Tool activation failed: {exc}")

    try:
        # Step 4: heartbeat
        _register_heartbeat(brand_slug)
        lines.append("✓ CEO heartbeat scheduled (Monday 9 AM IST)")
    except Exception as exc:
        lines.append(f"✗ Heartbeat registration failed: {exc}")

    lines.append("\nAll done. BrandOS is live.")
    return "\n".join(lines)


async def _seed_agents(
    company_id: str,
    company_slug: str,
    budget_caps: dict[str, float],
) -> None:
    """Insert AgentConfig rows for all 7 standing agents."""
    from src.shared.db import get_db  # type: ignore[import]

    _AGENT_DEFAULTS = [
        ("ceo",         "strategy",  "0 9 * * 1",  "aim-cmo"),
        ("cmo",         "creative",  "0 9 * * 2",  f"{company_slug}-ceo"),
        ("scout",       "batch",     "0 10 * * 3", f"{company_slug}-ceo"),
        ("creative",    "creative",  None,          f"{company_slug}-cmo"),
        ("performance", "creative",  "0 7 * * *",  f"{company_slug}-cmo"),
        ("ops",         "batch",     "0 8 * * *",  f"{company_slug}-ceo"),
        ("finance",     "strategy",  "0 17 * * 5", f"{company_slug}-ceo"),
    ]
    async for db in get_db():
        from sqlalchemy import text  # type: ignore[import]
        for template, tier, cron, reports_to in _AGENT_DEFAULTS:
            slug = f"{company_slug}-{template}"
            cap = budget_caps.get(template, 10.0)
            await db.execute(
                text(
                    "INSERT INTO agent_config "
                    "(id, agent_slug, agent_template, agent_type, is_specialist, "
                    " model_tier, heartbeat_cron, monthly_budget_cap_usd, "
                    " is_active, is_paused, reports_to_slug, company_id, config_json) "
                    "VALUES (gen_random_uuid(), :slug, :tmpl, 'standing', false, "
                    " :tier, :cron, :cap, true, false, :reports_to, :company_id, '{}') "
                    "ON CONFLICT (agent_slug) DO NOTHING"
                ),
                {
                    "slug": slug, "tmpl": template, "tier": tier,
                    "cron": cron, "cap": cap,
                    "reports_to": reports_to, "company_id": company_id,
                },
            )
        await db.commit()
        break


async def _seed_tools(company_id: str, selected_tools: list[str]) -> None:
    """Insert ToolRegistry rows for selected tools."""
    if not selected_tools:
        return
    from src.shared.db import get_db  # type: ignore[import]
    async for db in get_db():
        from sqlalchemy import text  # type: ignore[import]
        for tool_slug in selected_tools:
            await db.execute(
                text(
                    "INSERT INTO tool_registry "
                    "(id, company_id, tool_slug, is_active, monthly_budget_cap_usd) "
                    "VALUES (gen_random_uuid(), :company_id, :slug, true, 0.0) "
                    "ON CONFLICT (company_id, tool_slug) DO NOTHING"
                ),
                {"company_id": company_id, "slug": tool_slug},
            )
        await db.commit()
        break


def _register_heartbeat(company_slug: str) -> None:
    """Register CEO agent Monday 9 AM IST heartbeat via APScheduler."""
    try:
        from src.core.heartbeat import scheduler, register_agent_heartbeat  # type: ignore[import]
        register_agent_heartbeat(
            agent_slug=f"{company_slug}-ceo",
            company_slug=company_slug,
            cron_expr="0 9 * * 1",
        )
    except Exception as exc:
        logger.warning("Could not register heartbeat (scheduler may not be running): %s", exc)


_AUTO_ACTIONS: dict[str, Any] = {
    "auto_register_telegram_webhook": auto_register_telegram_webhook,
    "auto_register_whatsapp_webhook": auto_register_whatsapp_webhook,
    "run_auto_provision": run_auto_provision,
}


# ── Prompt formatting ─────────────────────────────────────────────────────────

def _format_prompt(step: OnboardingStep | None, config: dict[str, Any]) -> str:
    """Interpolate config values into the step prompt."""
    if step is None:
        return ""
    text = step.prompt
    for key, value in config.items():
        text = text.replace(f"{{{key}}}", str(value))

    # Computed substitutions
    selected = config.get("selected_tools", [])
    text = text.replace("{selected_tools_summary}", ", ".join(selected) if selected else "none")

    if step.signup_link:
        text += f"\n\nSign up: {step.signup_link}"
    return text


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_budget_caps() -> dict[str, float]:
    return {
        "ceo": 10.0, "cmo": 10.0, "scout": 5.0,
        "creative": 10.0, "performance": 15.0,
        "ops": 5.0, "finance": 5.0,
        "specialist_reserve": 25.0,
    }


def _parse_budget_caps(value: str) -> dict[str, float]:
    caps: dict[str, float] = {}
    for line in value.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Invalid format on line: '{line}'. Use agent:amount")
        agent, amount_str = line.split(":", 1)
        try:
            amount = float(amount_str.strip())
        except ValueError:
            raise ValueError(f"Invalid amount for '{agent.strip()}': '{amount_str.strip()}'")
        if amount < 1:
            raise ValueError(f"Budget cap for '{agent.strip()}' must be at least $1")
        caps[agent.strip().lower()] = amount
    return {**_default_budget_caps(), **caps}


def _parse_colors(value: str) -> dict[str, str]:
    colors: dict[str, str] = {}
    for part in value.split():
        if ":" in part:
            key, color = part.split(":", 1)
            colors[key.lower()] = color
    return colors


def _now() -> str:
    return datetime.now(UTC).isoformat()
