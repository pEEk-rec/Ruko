"""Loads and compiles ``data/policy/guardrails.yaml`` into ready-to-use pattern sets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ruko.data_files import load_yaml
from ruko.guardrails.normalize import strip_zero_width
from ruko.models.common import RefusalClass

_FLAGS = re.IGNORECASE | re.UNICODE


def _compile_all(patterns: list[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(strip_zero_width(p), _FLAGS) for p in patterns)


def _flatten_by_language(block: dict[str, list[str]]) -> tuple[re.Pattern[str], ...]:
    # Every language's patterns apply to every input: that is how code-mixed text
    # ("bhai kya ye stock badhega?") is caught regardless of the detected language.
    patterns: list[str] = []
    for language_patterns in block.values():
        patterns.extend(language_patterns)
    return _compile_all(patterns)


@dataclass(frozen=True)
class RefusalRule:
    """Compiled patterns and template keys for one refusal class."""

    refusal_class: RefusalClass
    message_key: str
    alternative_key: str
    patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class GuardrailPolicy:
    """Everything the intent gate, sensitive-data detector and output filter need."""

    version: str
    refusal_rules: tuple[RefusalRule, ...]
    verdict_patterns: tuple[re.Pattern[str], ...]
    injection_patterns: tuple[re.Pattern[str], ...]
    sensitive_message_key: str
    sensitive_alternative_key: str
    sensitive_patterns: dict[str, tuple[re.Pattern[str], ...]]
    card_number_pattern: re.Pattern[str]
    output_fallback_key: str
    output_forbidden: dict[str, tuple[re.Pattern[str], ...]]
    name_blocklist: tuple[re.Pattern[str], ...]

    def refusal_rule(self, refusal_class: RefusalClass) -> RefusalRule | None:
        """Return the rule for a refusal class, if it has one."""
        for rule in self.refusal_rules:
            if rule.refusal_class == refusal_class:
                return rule
        return None


def build_policy(raw: dict[str, Any]) -> GuardrailPolicy:
    """Compile a parsed guardrails YAML document.

    Args:
        raw: The parsed YAML.

    Returns:
        The compiled policy.
    """
    rules = tuple(
        RefusalRule(
            refusal_class=RefusalClass(name),
            message_key=spec["message_key"],
            alternative_key=spec["alternative_key"],
            patterns=_flatten_by_language(spec["patterns"]),
        )
        for name, spec in raw["refusal_classes"].items()
    )
    sensitive = raw["sensitive_data"]
    output = raw["output_filter"]
    names = tuple(
        re.compile(r"(?<![a-z0-9])" + re.escape(name.lower()) + r"(?![a-z0-9])", _FLAGS)
        for name in output["name_blocklist"]
    )
    return GuardrailPolicy(
        version=str(raw["version"]),
        refusal_rules=rules,
        verdict_patterns=_flatten_by_language(raw["verdict_requests"]),
        injection_patterns=_compile_all(raw["injection_cues"]),
        sensitive_message_key=sensitive["message_key"],
        sensitive_alternative_key=sensitive["alternative_key"],
        sensitive_patterns={k: _compile_all(v) for k, v in sensitive["patterns"].items()},
        card_number_pattern=re.compile(sensitive["card_number_regex"]),
        output_fallback_key=output["fallback_key"],
        output_forbidden={k: _compile_all(v) for k, v in output["forbidden"].items()},
        name_blocklist=names,
    )


@lru_cache(maxsize=1)
def get_policy() -> GuardrailPolicy:
    """Return the compiled guardrail policy from the data directory (cached)."""
    return build_policy(load_yaml("policy", "guardrails.yaml"))
