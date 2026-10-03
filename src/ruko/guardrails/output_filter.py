"""Output filter: the last check on every string Ruko sends out.

It looks for trade directives, return promises, safety claims, price predictions and
broker / platform names. A violating string is replaced by a safe fallback and only
the violation *category* is recorded, never the text.
"""

from __future__ import annotations

from dataclasses import dataclass

from ruko.guardrails.normalize import deobfuscate, normalize
from ruko.guardrails.policy import GuardrailPolicy, get_policy


@dataclass(frozen=True)
class FilterResult:
    """Outcome of filtering one string."""

    text: str
    blocked: bool
    categories: tuple[str, ...] = ()


def find_violations(text: str, policy: GuardrailPolicy | None = None) -> list[str]:
    """Return the categories of forbidden content found in a string (empty if clean).

    Args:
        text: Any outgoing text.
        policy: Optional policy override.

    Returns:
        Sorted category names such as ``["return_promise"]``.
    """
    policy = policy or get_policy()
    normalized = normalize(text)
    variants = (normalized, deobfuscate(normalized))
    found = {
        category
        for category, patterns in policy.output_forbidden.items()
        if any(p.search(v) for p in patterns for v in variants)
    }
    if any(p.search(v) for p in policy.name_blocklist for v in variants):
        found.add("named_product_or_broker")
    return sorted(found)


def filter_text(text: str, fallback: str, policy: GuardrailPolicy | None = None) -> FilterResult:
    """Return the text unchanged if clean, otherwise the fallback.

    Args:
        text: Outgoing text.
        fallback: Safe replacement text (itself checked; must be clean).
        policy: Optional policy override.

    Returns:
        A ``FilterResult``.

    Raises:
        ValueError: If the fallback itself violates the policy (a data bug).
    """
    violations = find_violations(text, policy)
    if not violations:
        return FilterResult(text=text, blocked=False)
    if find_violations(fallback, policy):
        raise ValueError("output fallback text violates the output filter")
    return FilterResult(text=fallback, blocked=True, categories=tuple(violations))
