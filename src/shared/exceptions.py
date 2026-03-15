"""
src/shared/exceptions.py

Custom exception hierarchy for BrandOS.
All layers raise typed exceptions — never raw Exception or ValueError.
"""

from __future__ import annotations


class BrandOSError(Exception):
    """Base exception for all BrandOS errors."""


# ── Budget ────────────────────────────────────────────────────────────────────


class BudgetExceededError(BrandOSError):
    """Raised when an agent's monthly token budget is exhausted."""

    def __init__(self, agent_slug: str, company_slug: str, cap_usd: float) -> None:
        self.agent_slug = agent_slug
        self.company_slug = company_slug
        self.cap_usd = cap_usd
        super().__init__(
            f"Agent '{agent_slug}' for brand '{company_slug}' has exceeded "
            f"its monthly budget cap of ${cap_usd:.2f}."
        )


# ── Auth ──────────────────────────────────────────────────────────────────────


class AuthenticationError(BrandOSError):
    """Invalid or missing API key."""


# ── Sanitizer ─────────────────────────────────────────────────────────────────


class InjectionDetectedError(BrandOSError):
    """Raised when the sanitizer detects a prompt injection attempt."""

    def __init__(self, source: str) -> None:
        self.source = source
        super().__init__(f"Prompt injection pattern detected in input from '{source}'.")


# ── Vault ─────────────────────────────────────────────────────────────────────


class SecretNotFoundError(BrandOSError):
    """Requested secret path does not exist in Infisical."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Secret not found at vault path: '{path}'.")


class VaultUnavailableError(BrandOSError):
    """Infisical vault is unreachable."""


# ── LLM ──────────────────────────────────────────────────────────────────────


class LLMProviderError(BrandOSError):
    """LLM provider returned an error or is unavailable."""

    def __init__(self, provider: str, detail: str) -> None:
        self.provider = provider
        super().__init__(f"LLM provider '{provider}' error: {detail}")


class ModelRouterError(BrandOSError):
    """Unknown task type passed to model router."""

    def __init__(self, task_type: str) -> None:
        self.task_type = task_type
        super().__init__(f"No model mapping for task type: '{task_type}'.")


# ── Brand isolation ───────────────────────────────────────────────────────────


class CrossBrandAccessError(BrandOSError):
    """Attempted cross-brand data or credential access."""

    def __init__(self, requesting: str, target: str) -> None:
        super().__init__(
            f"Brand isolation violation: '{requesting}' attempted to access '{target}' data."
        )


# ── Tool ─────────────────────────────────────────────────────────────────────


class ToolNotRegisteredError(BrandOSError):
    """Agent tried to use a tool not registered for its brand."""

    def __init__(self, tool_slug: str, company_slug: str) -> None:
        super().__init__(
            f"Tool '{tool_slug}' is not registered for brand '{company_slug}'."
        )


class ToolExecutionError(BrandOSError):
    """A tool call to an external API failed."""

    def __init__(self, tool_slug: str, detail: str) -> None:
        self.tool_slug = tool_slug
        super().__init__(f"Tool '{tool_slug}' execution failed: {detail}")


# ── Agent / Company ───────────────────────────────────────────────────────────


class CompanyNotFoundError(BrandOSError):
    def __init__(self, slug: str) -> None:
        self.slug = slug
        super().__init__(f"Company not found: '{slug}'.")


class AgentNotFoundError(BrandOSError):
    def __init__(self, agent_slug: str, company_slug: str) -> None:
        self.agent_slug = agent_slug
        self.company_slug = company_slug
        super().__init__(f"Agent '{agent_slug}' not found for brand '{company_slug}'.")


class TicketNotFoundError(BrandOSError):
    def __init__(self, ticket_id: str) -> None:
        self.ticket_id = ticket_id
        super().__init__(f"Ticket not found: '{ticket_id}'.")


class GovernanceError(BrandOSError):
    """Raised for invalid governance state transitions or unauthorized actions."""


class AgentWindDownError(BrandOSError):
    def __init__(self, agent_slug: str) -> None:
        super().__init__(f"Agent '{agent_slug}' has been wound down and cannot execute tasks.")


class AgentPausedError(BrandOSError):
    def __init__(self, agent_slug: str) -> None:
        super().__init__(f"Agent '{agent_slug}' is paused. Resume via governance before running tasks.")


class ImmutableAuditError(BrandOSError):
    def __init__(self, entry_id: str) -> None:
        super().__init__(f"Audit entry '{entry_id}' is already rolled back and cannot be modified.")
