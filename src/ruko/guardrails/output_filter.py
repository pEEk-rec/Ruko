"""Output filter: the last check on every string Ruko sends out.

A thin wrapper over the assertion-level validator (``output_validator``): a violating
string is replaced by a safe fallback and only the violation *category* is recorded,
never the text. Without a response type the strictest rules apply.
"""

from __future__ import annotations

from dataclasses import dataclass

from ruko.guardrails.output_validator import STRICT, validate


@dataclass(frozen=True)
class FilterResult:
    """Outcome of filtering one string."""

    text: str
    blocked: bool
    categories: tuple[str, ...] = ()


def find_violations(text: str, response_type: str = STRICT) -> list[str]:
    """Return the violation categories in a string (empty if allowed).

    Args:
        text: Any outgoing text.
        response_type: The template's response type; ``strict`` allows no claim reporting.

    Returns:
        Sorted category names such as ``["return_claim"]``.
    """
    return validate(text, response_type)


def filter_text(text: str, fallback: str, response_type: str = STRICT) -> FilterResult:
    """Return the text unchanged if allowed, otherwise the fallback.

    Args:
        text: Outgoing text.
        fallback: Safe replacement text (itself checked; must be clean).
        response_type: The template's response type.

    Returns:
        A ``FilterResult``.

    Raises:
        ValueError: If the fallback itself violates the policy (a data bug).
    """
    violations = find_violations(text, response_type)
    if not violations:
        return FilterResult(text=text, blocked=False)
    if find_violations(fallback):
        raise ValueError("output fallback text violates the output policy")
    return FilterResult(text=fallback, blocked=True, categories=tuple(violations))
