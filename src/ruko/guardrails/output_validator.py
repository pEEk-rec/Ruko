"""Assertion-level output validator: checks what Ruko *asserts*, not only which words appear.

Rules (``data/policy/output_policy.yaml`` + the always-forbidden lists in
``data/policy/guardrails.yaml``):

1. Always forbidden, in any response type: trade directives, price or outcome
   predictions, named brokers/apps/platforms, and verdicts ("this is a scam").
2. Some response types add their own forbidden patterns (``type_forbidden``): a
   ``calculation`` never says "you will get" or "expected return".
3. Claim terms (guaranteed/assured returns, "safe", "legit", "genuine") may only be
   *reported*: the template's response type must allow reporting, and the same sentence
   must carry a reporting frame ("the message contains...", "SEBI does not allow...").
   "This message contains a guaranteed-return claim" passes as a ``signal_report``;
   "This is guaranteed" or "This app is safe" never passes.

Violations return category names only; the text itself is never logged.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel

from ruko.data_files import load_yaml
from ruko.errors import ErrorCode, RukoError
from ruko.guardrails.normalize import deobfuscate, normalize, strip_zero_width
from ruko.guardrails.policy import GuardrailPolicy, get_policy
from ruko.observability import log_event

_FLAGS = re.IGNORECASE | re.UNICODE
_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+|\n+")
ResponseT = TypeVar("ResponseT", bound=BaseModel)
STRICT = "strict"
"""Response type used for text without a template: nothing may be reported."""

USER_TEXT_FIELDS = frozenset(
    {"headline", "numbers_text", "rules_text", "text", "question", "title", "body", "label",
     "override_label", "message", "alternative", "evidence_checklist", "draft_complaint",
     "highlights", "explanation", "assumptions", "lines", "brief", "summary"}
)  # fmt: skip
"""Response fields that carry user-facing text (checked by ``response_violations``)."""


@dataclass(frozen=True)
class OutputPolicy:
    """The compiled output policy."""

    fallback_key: str
    may_report: dict[str, bool]
    verdicts: tuple[re.Pattern[str], ...]
    claims: dict[str, tuple[re.Pattern[str], ...]]
    frames: tuple[re.Pattern[str], ...]
    type_forbidden: dict[str, tuple[re.Pattern[str], ...]]

    def known_type(self, response_type: str) -> bool:
        """True if the response type is declared in the policy."""
        return response_type in self.may_report or response_type == STRICT


def _compile(patterns: list[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(strip_zero_width(p), _FLAGS) for p in patterns)


@lru_cache(maxsize=1)
def get_output_policy() -> OutputPolicy:
    """Load ``data/policy/output_policy.yaml`` (cached)."""
    raw = load_yaml("policy", "output_policy.yaml")
    frames = [p for patterns in raw["reporting_frames"].values() for p in patterns]
    return OutputPolicy(
        fallback_key=raw["fallback_key"],
        may_report={k: bool(v["may_report_claims"]) for k, v in raw["response_types"].items()},
        verdicts=_compile(raw["verdicts"]),
        claims={k: _compile(v) for k, v in raw["claims"].items()},
        frames=_compile(frames),
        type_forbidden={k: _compile(v) for k, v in (raw.get("type_forbidden") or {}).items()},
    )


def _variants(text: str) -> tuple[str, str]:
    normalized = normalize(text)
    return normalized, deobfuscate(normalized)


def _hits(patterns: tuple[re.Pattern[str], ...], variants: tuple[str, ...]) -> bool:
    return any(p.search(v) for p in patterns for v in variants)


def always_forbidden(text: str, guard: GuardrailPolicy | None = None) -> list[str]:
    """Return always-forbidden categories found in the text (any response type)."""
    guard = guard or get_policy()
    variants = _variants(text)
    found = {cat for cat, pats in guard.output_forbidden.items() if _hits(pats, variants)}
    if _hits(guard.name_blocklist, variants):
        found.add("named_product_or_broker")
    if _hits(get_output_policy().verdicts, variants):
        found.add("verdict")
    return sorted(found)


def claim_violations(
    text: str, response_type: str, policy: OutputPolicy | None = None
) -> list[str]:
    """Return claim categories that Ruko would be *asserting* (not reporting) in the text."""
    policy = policy or get_output_policy()
    may_report = policy.may_report.get(response_type, False)
    found: set[str] = set()
    for sentence in _SENTENCE_END.split(text):
        variants = _variants(sentence)
        for category, patterns in policy.claims.items():
            if not _hits(patterns, variants):
                continue
            if not (may_report and _hits(policy.frames, variants)):
                found.add(category)
    return sorted(found)


def type_violations(text: str, response_type: str, policy: OutputPolicy | None = None) -> list[str]:
    """Return ``<type>_assertion`` if the text breaks a rule specific to its response type."""
    policy = policy or get_output_policy()
    patterns = policy.type_forbidden.get(response_type)
    if patterns and _hits(patterns, _variants(text)):
        return [f"{response_type}_assertion"]
    return []


def validate(text: str, response_type: str = STRICT) -> list[str]:
    """Return every violation category for one outgoing string (empty means allowed).

    Args:
        text: The rendered string.
        response_type: The template's declared response type (``strict`` if none).

    Returns:
        Sorted category names, e.g. ``["return_claim", "verdict"]``.
    """
    found = set(always_forbidden(text)) | set(claim_violations(text, response_type))
    return sorted(found | set(type_violations(text, response_type)))


def _collect(value: object, field: str | None, out: list[str]) -> None:
    if isinstance(value, BaseModel):
        for name in type(value).model_fields:
            _collect(getattr(value, name), name, out)
    elif isinstance(value, list):
        for item in value:
            _collect(item, field, out)
    elif isinstance(value, str) and field in USER_TEXT_FIELDS:
        out.append(value)


def user_facing_texts(response: BaseModel) -> list[str]:
    """Return every user-facing string in a response model."""
    texts: list[str] = []
    _collect(response, None, texts)
    return texts


def response_violations(response: BaseModel) -> list[str]:
    """Check a whole response as a final safety net.

    Looks for always-forbidden content and for claims outside a reporting frame in every
    user-facing string. Templates were already validated by type when rendered.
    """
    found: set[str] = set()
    kind = getattr(response, "kind", None)
    for text in user_facing_texts(response):
        found |= set(always_forbidden(text))
        found |= set(claim_violations(text, "signal_report"))
        if isinstance(kind, str):
            found |= set(type_violations(text, kind))
    return sorted(found)


def ensure_safe(response: ResponseT) -> ResponseT:
    """Return the response if it passes the final check; otherwise raise ``OUTPUT_BLOCKED``.

    Only the violation categories are logged, never the text.
    """
    violations = response_violations(response)
    if violations:
        log_event("output_blocked", logging.ERROR, error_code=",".join(violations))
        raise RukoError(ErrorCode.OUTPUT_BLOCKED)
    return response
