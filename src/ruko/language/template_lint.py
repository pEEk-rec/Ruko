"""Template linter: completeness, slot consistency and output-filter safety.

Rules:

1. Every key that exists in any locale exists in every locale.
2. A key has the same ``{slot}`` names in every locale.
3. No template text is empty.
4. Every template declares a known ``response_type`` (same in every locale) and passes the
   assertion-level output validator for that type (slots filled with neutral samples).
5. Every key the code depends on (error messages, guardrail responses, clarifying
   questions, cards, base rates, recovery,
   journal, pause screen, calculators) exists.
"""

from __future__ import annotations

from ruko.data_files import load_yaml
from ruko.engine.base_rates import CAVEAT_DESCRIPTIVE, CAVEAT_GROUP, TEXT_KEY_BY_SOURCE
from ruko.errors import ErrorCode, message_key_for
from ruko.guardrails.output_filter import find_violations
from ruko.guardrails.output_validator import get_output_policy
from ruko.guardrails.policy import GuardrailPolicy, get_policy
from ruko.journal.review import TEMPLATE_KEYS as JOURNAL_TEMPLATE_KEYS
from ruko.language.templates import TemplateStore, get_template_store
from ruko.orchestrator.pause import FIXED_KEYS as PAUSE_TEMPLATE_KEYS
from ruko.tools.calculate import TEMPLATE_KEYS as CALCULATION_TEMPLATE_KEYS

SAMPLE_SLOT_VALUE = "12"


def required_keys(policy: GuardrailPolicy) -> set[str]:
    """Return template keys that code references directly."""
    keys = {message_key_for(code) for code in ErrorCode}
    keys |= {policy.output_fallback_key, policy.sensitive_message_key}
    keys |= {policy.sensitive_alternative_key, "verdict.cannot_vouch"}
    for rule in policy.refusal_rules:
        keys |= {rule.message_key, rule.alternative_key}
    keys |= {*TEXT_KEY_BY_SOURCE.values(), CAVEAT_DESCRIPTIVE, CAVEAT_GROUP}
    for fact in load_yaml("facts", "base_rates.yaml")["facts"]:
        if "product_class" in fact["applies_to"]:
            keys.add(f"base_rate.group.{fact['group_key']}")
    for card in load_yaml("cards", "catalog.yaml")["cards"]:
        keys.add(f"card.{card['id']}.title")
        if card["slots"] != "base_rate":
            keys.add(f"card.{card['id']}.body")
    keys |= JOURNAL_TEMPLATE_KEYS
    keys |= PAUSE_TEMPLATE_KEYS
    keys |= CALCULATION_TEMPLATE_KEYS
    pause = load_yaml("policy", "pause.yaml")
    keys |= {*pause["question_by_category"].values(), pause["default_question"]}
    recovery = load_yaml("policy", "recovery.yaml")
    keys.add("recovery.no_promise")
    for spec in recovery["scenarios"].values():
        keys |= {f"recovery.step.{step['id']}" for step in spec["steps"]}
        keys |= {f"recovery.evidence.{item}" for item in spec["evidence"]}
        keys.add(f"recovery.draft.{spec['draft']}")
    clarify = load_yaml("policy", "clarify.yaml")
    for item in clarify["fields"]:
        keys.add(item["question_key"])
        keys |= {f"clarify.{item['field']}.option.{value}" for value in item["options"]}
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
            if not get_output_policy().known_type(template.response_type):
                problems.append(f"unknown response_type {locale}: {key}")
            if reference is not None and template.response_type != reference.response_type:
                problems.append(f"response_type differs {locale}: {key}")
            violations = find_violations(sample, template.response_type)
            if violations:
                problems.append(f"output validator {locale}: {key} -> {','.join(violations)}")
    return problems
