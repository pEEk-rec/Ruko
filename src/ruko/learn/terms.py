"""One shared word layer: the glossary terms used anywhere in a Ruko response.

Every screen of the app (a pause, a content report, a calculation, a lesson, a glossary
answer) explains its own words the same way: tap a word, see a short explanation. The words
come from the same curated alias patterns that answer a "what is X?" question; the short
explanation behind each word is a human-checked template (``glossary.<id>.brief``).

Only Ruko's own rendered texts are scanned (``user_facing_texts``): never the user's message
or the quotes taken from it. Nothing here is written by the LLM.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

from pydantic import BaseModel

from ruko.cards.glossary import GlossaryTerm, get_glossary
from ruko.guardrails.output_validator import user_facing_texts
from ruko.language.templates import Renderer
from ruko.models.responses import TermHit

ResponseT = TypeVar("ResponseT", bound=BaseModel)

MAX_TERMS_PER_TEXT = 6
"""More highlighted words than this stop being a reading aid and become noise."""


def _first_match(term: GlossaryTerm, text: str) -> tuple[int, int] | None:
    """Span of the earliest alias match of one term, or None."""
    spans = [m.span() for a in term.aliases if (m := a.search(text))]
    return min(spans, default=None)


def find_terms(
    text: str,
    renderer: Renderer,
    *,
    exclude: Iterable[str] = (),
    limit: int = MAX_TERMS_PER_TEXT,
) -> list[TermHit]:
    """Return the glossary terms named in a Ruko text, each once, in reading order.

    Args:
        text: A rendered Ruko text (a lesson body, a card, a glossary answer).
        renderer: Renderer for the user's locale (runs the output validator on each brief).
        exclude: Term IDs to leave out (for example the term the answer is about).
        limit: Most terms to return; the earliest in the text win.

    Returns:
        One ``TermHit`` per term: its exact words in the text, its name and its brief.
    """
    skip = set(exclude)
    found: list[tuple[int, int, GlossaryTerm]] = []
    for term in get_glossary().terms:
        if term.id in skip:
            continue
        span = _first_match(term, text)
        if span is not None:
            found.append((*span, term))
    found.sort(key=lambda item: item[0])
    hits: list[TermHit] = []
    taken_until = -1
    for start, end, term in found:
        if start < taken_until:  # overlaps a word already taken
            continue
        hits.append(
            TermHit(
                id=term.id,
                match=text[start:end],
                title=renderer.text(term.title_key),
                brief=renderer.text(term.brief_key),
            )
        )
        taken_until = end
        if len(hits) == limit:
            break
    return hits


MAX_LEXICON = 14
"""Words offered per response; more than this stops being a reading aid."""


def lexicon(
    texts: Iterable[str],
    renderer: Renderer,
    *,
    exclude: Iterable[str] = (),
    limit: int = MAX_LEXICON,
) -> list[TermHit]:
    """Return the terms used across several texts, one entry per distinct wording.

    The same term can appear as "SIP" in one text and "SIPs" in another; each wording is its
    own entry so the app can find it, and the brief is rendered once per term.

    Args:
        texts: Ruko's rendered texts (one response).
        renderer: Renderer for the user's locale.
        exclude: Term IDs to leave out (for example the term a glossary answer is about).
        limit: Most terms (not wordings) to return, in order of first appearance.
    """
    skip = set(exclude)
    first_seen: dict[str, int] = {}
    wordings: dict[str, list[str]] = {}
    for position, text in enumerate(texts):
        for hit in find_terms(text, renderer, exclude=skip, limit=limit):
            first_seen.setdefault(hit.id, position)
            if hit.match not in wordings.setdefault(hit.id, []):
                wordings[hit.id].append(hit.match)
    kept = sorted(first_seen, key=first_seen.__getitem__)[:limit]
    glossary = {term.id: term for term in get_glossary().terms}
    hits: list[TermHit] = []
    for term_id in kept:
        title = renderer.text(glossary[term_id].title_key)
        brief = renderer.text(glossary[term_id].brief_key)
        hits += [TermHit(id=term_id, match=m, title=title, brief=brief) for m in wordings[term_id]]
    return hits


def with_terms(response: ResponseT) -> ResponseT:
    """Attach the shared word layer to a response that has a ``terms`` field.

    A glossary answer leaves out its own term. Responses without the field are returned as
    they are.
    """
    if "terms" not in type(response).model_fields:
        return response
    meta = getattr(response, "meta", None)
    renderer = Renderer(meta.locale if meta is not None else "en")
    own = getattr(response, "term", None)
    # Chip rows ("related terms") are lists of names, not reading text: leave them out.
    blank = {"terms": [], **({"related": []} if "related" in type(response).model_fields else {})}
    texts = user_facing_texts(response.model_copy(update=blank))
    found = lexicon(texts, renderer, exclude={own} if own else ())
    return response.model_copy(update={"terms": found})
