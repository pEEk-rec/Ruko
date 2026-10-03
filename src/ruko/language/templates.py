"""Localized templates and the renderer that every outgoing string goes through.

Templates live in ``data/templates/{locale}.yaml``. Each has ``text`` (with ``{slot}``
placeholders) and ``status`` (``draft`` or ``human_verified``). Adding a language means
adding one YAML file and enabling the locale in settings.

``Renderer`` is the only way the backend produces user-facing text:
render the template (falling back to English if a key is missing in the locale), run
the output filter, and record metadata (missing keys, draft count, blocked count).
"""

from __future__ import annotations

import string
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from ruko.data_files import data_dir, load_yaml
from ruko.guardrails.output_filter import filter_text
from ruko.guardrails.policy import get_policy

FALLBACK_LOCALE = "en"
TemplateStatus = Literal["draft", "human_verified"]


@dataclass(frozen=True)
class Template:
    """One localized template."""

    key: str
    text: str
    status: TemplateStatus

    @property
    def slots(self) -> frozenset[str]:
        """Return the names of the ``{slot}`` placeholders in the text."""
        return frozenset(
            name for _, name, _, _ in string.Formatter().parse(self.text) if name is not None
        )


class TemplateStore:
    """All templates for all locales, indexed by locale and key."""

    def __init__(self, templates: dict[str, dict[str, Template]]) -> None:
        self._templates = templates

    def locales(self) -> list[str]:
        """Return the locales that have a template file."""
        return sorted(self._templates)

    def keys(self, locale: str) -> set[str]:
        """Return the template keys defined for a locale."""
        return set(self._templates.get(locale, {}))

    def get(self, locale: str, key: str) -> Template | None:
        """Return a template, or None if the locale does not define the key."""
        return self._templates.get(locale, {}).get(key)


def _parse_locale_file(raw: dict) -> dict[str, Template]:
    templates: dict[str, Template] = {}
    for key, spec in (raw.get("templates") or {}).items():
        status = spec.get("status", "draft")
        if status not in ("draft", "human_verified"):
            raise ValueError(f"template {key} has invalid status")
        templates[key] = Template(key=key, text=str(spec["text"]).strip(), status=status)
    return templates


@lru_cache(maxsize=1)
def get_template_store() -> TemplateStore:
    """Load every ``data/templates/*.yaml`` file (cached)."""
    templates: dict[str, dict[str, Template]] = {}
    for path in sorted((data_dir() / "templates").glob("*.yaml")):
        raw = load_yaml("templates", path.name)
        templates[str(raw["locale"])] = _parse_locale_file(raw)
    return TemplateStore(templates)


class MissingSlotError(KeyError):
    """A template needs a slot value that was not provided (a code bug)."""


@dataclass
class Renderer:
    """Renders templates for one locale and records rendering metadata.

    Attributes:
        locale: Requested locale.
        store: Template store (defaults to the data files).
        missing_keys: Keys that fell back to English.
        draft_count: Number of rendered templates still in draft status.
        blocked_count: Number of strings replaced by the output filter.
    """

    locale: str
    store: TemplateStore = field(default_factory=get_template_store)
    missing_keys: list[str] = field(default_factory=list)
    draft_count: int = 0
    blocked_count: int = 0

    def _lookup(self, key: str) -> Template:
        template = self.store.get(self.locale, key)
        if template is None:
            if key not in self.missing_keys:
                self.missing_keys.append(key)
            template = self.store.get(FALLBACK_LOCALE, key)
        if template is None:
            raise KeyError(f"template key not defined in any locale: {key}")
        return template

    def raw(self, key: str, **slots: object) -> str:
        """Render a template without the output filter (used by the linter only)."""
        template = self._lookup(key)
        missing = template.slots - slots.keys()
        if missing:
            raise MissingSlotError(f"{key} needs slots {sorted(missing)}")
        return template.text.format_map({k: str(v) for k, v in slots.items()})

    def text(self, key: str, **slots: object) -> str:
        """Render a template, run the output filter, and return safe text.

        Args:
            key: Template key.
            **slots: Values for the template's placeholders.

        Returns:
            The rendered text, or the localized fallback if the filter blocked it.
        """
        template = self._lookup(key)
        if template.status == "draft":
            self.draft_count += 1
        rendered = self.raw(key, **slots)
        return self.filtered(rendered)

    def filtered(self, text: str) -> str:
        """Run any text (template or LLM) through the output filter."""
        policy = get_policy()
        fallback = self.raw(policy.output_fallback_key)
        result = filter_text(text, fallback, policy)
        if result.blocked:
            self.blocked_count += 1
        return result.text
