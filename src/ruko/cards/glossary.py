"""The curated glossary for the ``learn`` stage (``data/glossary/catalog.yaml``).

Terms are matched with alias patterns in every language. Texts are human-checked
templates (``glossary.<id>.title`` / ``.body``); the LLM never writes an explanation.
An unknown term gets a polite "not in Ruko's glossary" line and the official pointer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from ruko.cards.catalog import resolve_fact
from ruko.data_files import load_yaml
from ruko.guardrails.normalize import normalize, strip_zero_width
from ruko.language.templates import Renderer
from ruko.models.common import SourceRef
from ruko.models.responses import TemplateRef

_FLAGS = re.IGNORECASE | re.UNICODE
NOT_FOUND_KEY = "glossary.not_found"
NOTE_KEY = "glossary.note"


@dataclass(frozen=True)
class GlossaryTerm:
    """One glossary entry."""

    id: str
    aliases: tuple[re.Pattern[str], ...]
    facts: tuple[str, ...]

    @property
    def title_key(self) -> str:
        """Template key of the title."""
        return f"glossary.{self.id}.title"

    @property
    def body_key(self) -> str:
        """Template key of the body."""
        return f"glossary.{self.id}.body"


@dataclass(frozen=True)
class Glossary:
    """All entries plus the fallback pointer."""

    terms: tuple[GlossaryTerm, ...]
    fallback_fact: str

    def template_keys(self) -> set[str]:
        """Every template key the glossary can render (for the linter)."""
        keys = {NOT_FOUND_KEY, NOTE_KEY}
        for term in self.terms:
            keys |= {term.title_key, term.body_key}
        return keys


@dataclass
class GlossaryContent:
    """A rendered glossary answer."""

    found: bool
    term: str | None
    title: str | None
    body: str
    sources: list[SourceRef]
    speak: list[TemplateRef] = field(default_factory=list)
    unverified_fact_ids: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def get_glossary() -> Glossary:
    """Load the glossary catalog (cached)."""
    raw = load_yaml("glossary", "catalog.yaml")
    terms = tuple(
        GlossaryTerm(
            id=t["id"],
            aliases=tuple(re.compile(strip_zero_width(a), _FLAGS) for a in t["aliases"]),
            facts=tuple(t.get("facts") or ()),
        )
        for t in raw["terms"]
    )
    return Glossary(terms=terms, fallback_fact=raw["fallback_fact"])


def find_term(text: str, glossary: Glossary | None = None) -> GlossaryTerm | None:
    """Return the first glossary entry whose aliases appear in the text, if any."""
    glossary = glossary or get_glossary()
    normalized = normalize(text)
    return next((t for t in glossary.terms if any(a.search(normalized) for a in t.aliases)), None)


def build_glossary(text: str, renderer: Renderer, show_unverified: bool = True) -> GlossaryContent:
    """Answer a learn-stage question from the curated glossary.

    Args:
        text: The user's question (matched in memory only).
        renderer: Renderer for the user's locale (runs the output validator).
        show_unverified: False in production: unverified source pointers are left out.

    Returns:
        The rendered entry with its sources, or the not-found line with the official pointer.
    """
    glossary = get_glossary()
    term = find_term(text, glossary)
    fact_ids = list(term.facts) if term else [glossary.fallback_fact]
    facts = [resolve_fact(f) for f in fact_ids]
    if not show_unverified:
        facts = [f for f in facts if f.source.verified_by_human]
    unverified = [f.fact_id for f in facts if not f.source.verified_by_human]
    sources = [f.source for f in facts]
    if term is None:
        return GlossaryContent(
            found=False,
            term=None,
            title=None,
            body=renderer.text(NOT_FOUND_KEY),
            sources=sources,
            speak=[TemplateRef(key=NOT_FOUND_KEY)],
            unverified_fact_ids=unverified,
        )
    body = f"{renderer.text(term.body_key)} {renderer.text(NOTE_KEY)}"
    return GlossaryContent(
        found=True,
        term=term.id,
        title=renderer.text(term.title_key),
        body=body,
        sources=sources,
        speak=[TemplateRef(key=k) for k in (term.title_key, term.body_key, NOTE_KEY)],
        unverified_fact_ids=unverified,
    )
