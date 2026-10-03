"""Template linter: completeness, slot consistency and output-filter safety.

Rules:

1. Every key that exists in any locale exists in every locale.
2. A key has the same ``{slot}`` names in every locale.
3. No template text is empty.
4. Every template passes the output filter (with slots filled by neutral sample values).
5. Every key the code depends on (error messages, guardrail responses) exists.
"""

from __future__ import annotations

from ruko.errors import ErrorCode, message_key_for
from ruko.guardrails.output_filter import find_violations
from ruko.guardrails.policy import GuardrailPolicy, get_policy
from ruko.language.templates import TemplateStore, get_template_store

SAMPLE_SLOT_VALUE = "12"


def required_keys(policy: GuardrailPolicy) -> set[str]:
    """Return template keys that code references directly."""
    keys = {message_key_for(code) for code in ErrorCode}
    keys |= {policy.output_fallback_key, policy.sensitive_message_key}
    keys |= {policy.sensitive_alternative_key, "verdict.cannot_vouch"}
    for rule in policy.refusal_rules:
        keys |= {rule.message_key, rule.alternative_key}
    return keys


def lint_templates(
    store: TemplateStore | None = None,
    policy: GuardrailPolicy | None = None,
    extra_required: set[str] | None = None,
) -> list[str]:
    """Return a list of human-readable problems (empty means the linter is green).

    Args:
        store: Template store to check (defaults to the data files).
        policy: Guardrail policy (defaults to the data file).
        extra_required: More keys that must exist (e.g. from cards or reason codes).

    Returns:
        Problems such as ``"missing kn: reason.borrowed_funds"``.
    """
    store = store or get_template_store()
    policy = policy or get_policy()
    problems: list[str] = []
    locales = store.locales()
    all_keys = set().union(*(store.keys(loc) for loc in locales)) if locales else set()

    for key in sorted(required_keys(policy) | (extra_required or set())):
        if key not in all_keys:
            problems.append(f"required key missing everywhere: {key}")

    for key in sorted(all_keys):
        reference = store.get("en", key)
        for locale in locales:
            template = store.get(locale, key)
            if template is None:
                problems.append(f"missing {locale}: {key}")
                continue
            if not template.text.strip():
                problems.append(f"empty {locale}: {key}")
            if reference is not None and template.slots != reference.slots:
                problems.append(f"slots differ {locale}: {key}")
            sample = template.text.format_map(dict.fromkeys(template.slots, SAMPLE_SLOT_VALUE))
            violations = find_violations(sample, policy)
            if violations:
                problems.append(f"output filter {locale}: {key} -> {','.join(violations)}")
    return problems
