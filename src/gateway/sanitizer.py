"""
src/gateway/sanitizer.py  (AM-23)

Prompt injection sanitizer.
ALL external data (email content, ad platform responses, supplier messages,
webhook payloads, user inputs) must pass through sanitize() before entering
any agent's context window. No exceptions.

Detects and strips:
  1. Prompt override instructions ("ignore previous instructions", "forget all")
  2. XML/HTML-style injection tags (<system>, <instructions>, <prompt>, etc.)
  3. Role-play/persona hijacking ("you are now", "act as", "pretend to be")
  4. Escape sequences and control characters
  5. Repeated suspicious instruction patterns
"""

from __future__ import annotations

import re
import unicodedata

from src.shared.exceptions import InjectionDetectedError

# ── Injection pattern definitions ─────────────────────────────────────────────

# Patterns that indicate a prompt override attempt
_OVERRIDE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|context|prompts?)\b", re.IGNORECASE),
    re.compile(r"\bforget\s+(all\s+)?(previous|prior|above|earlier|your)\b", re.IGNORECASE),
    re.compile(r"\bdisregard\s+(all\s+)?(previous|prior|above)\b", re.IGNORECASE),
    re.compile(r"\bnew\s+instructions?\s*:\s*", re.IGNORECASE),
    re.compile(r"\bsystem\s+prompt\s*:\s*", re.IGNORECASE),
    re.compile(r"\byour\s+real\s+instructions?\b", re.IGNORECASE),
    re.compile(r"\bdo\s+not\s+follow\s+your\b", re.IGNORECASE),
    re.compile(r"\boverride\s+(all\s+)?(instructions?|constraints?|rules?)\b", re.IGNORECASE),
]

# XML/HTML tags that signal prompt injection via structured markup
_TAG_PATTERN = re.compile(
    r"<\s*/?\s*(?:system|instructions?|prompt|context|human|assistant|user|role|override|jailbreak)[^>]*>",
    re.IGNORECASE,
)

# Role-play / persona hijacking
_ROLEPLAY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"\bact\s+as\s+(?:if\s+you\s+(?:are|were)\s+)?(?:a\s+|an\s+)?(?!the\s+marketing)", re.IGNORECASE),
    re.compile(r"\bpretend\s+(?:you\s+are|to\s+be)\b", re.IGNORECASE),
    re.compile(r"\bswitch\s+(?:your\s+)?(?:persona|role|mode)\b", re.IGNORECASE),
    re.compile(r"\byour\s+(?:true\s+)?(?:identity|purpose|goal)\s+is\b", re.IGNORECASE),
]

# Control characters that don't belong in clean text
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _strip_xml_tags(text: str) -> str:
    """Remove injection-related XML/HTML tags (content is kept, tags are stripped)."""
    return _TAG_PATTERN.sub("", text)


def _strip_control_chars(text: str) -> str:
    """Remove non-printable control characters."""
    return _CONTROL_CHAR_PATTERN.sub("", text)


def _normalize_unicode(text: str) -> str:
    """Normalize unicode to NFC — defuses some homoglyph attacks."""
    return unicodedata.normalize("NFC", text)


def _detect_injection(text: str) -> str | None:
    """
    Return the name of the first injection pattern detected, or None if clean.
    """
    for pattern in _OVERRIDE_PATTERNS:
        if pattern.search(text):
            return "override_instruction"
    if _TAG_PATTERN.search(text):
        return "xml_tag_injection"
    for pattern in _ROLEPLAY_PATTERNS:
        if pattern.search(text):
            return "roleplay_hijack"
    return None


def sanitize(text: str, source: str = "unknown") -> str:
    """
    Sanitize external text before it enters any agent context window.

    Processing steps:
      1. Normalize unicode
      2. Strip control characters
      3. Detect injection patterns — raise InjectionDetectedError if found
      4. Strip injection XML tags (defence-in-depth after detection)

    Args:
        text: Raw external input.
        source: Descriptive label for logging (e.g. "whatsapp_webhook", "meta_ads_response").

    Returns:
        Cleaned text safe for agent consumption.

    Raises:
        InjectionDetectedError: if a known injection pattern is detected.
    """
    text = _normalize_unicode(text)
    text = _strip_control_chars(text)

    injection_type = _detect_injection(text)
    if injection_type:
        raise InjectionDetectedError(source=f"{source}:{injection_type}")

    # Strip tags even if not raising (defence-in-depth)
    text = _strip_xml_tags(text)

    return text


def sanitize_dict(data: dict, source: str = "unknown") -> dict:
    """
    Recursively sanitize all string values in a dict.
    Useful for sanitizing entire webhook payloads.
    """
    result: dict = {}
    for k, v in data.items():
        if isinstance(v, str):
            result[k] = sanitize(v, source=f"{source}.{k}")
        elif isinstance(v, dict):
            result[k] = sanitize_dict(v, source=f"{source}.{k}")
        elif isinstance(v, list):
            result[k] = [
                sanitize(item, source=f"{source}.{k}[{i}]") if isinstance(item, str)
                else sanitize_dict(item, source=f"{source}.{k}[{i}]") if isinstance(item, dict)
                else item
                for i, item in enumerate(v)
            ]
        else:
            result[k] = v
    return result
