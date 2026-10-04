"""The Learn list: lessons anyone can read at any time, ordered for this person.

Decision-triggered lessons (``learn/select.py``) answer "what does this decision need?".
This module answers "what is worth knowing next?" and does not wait for a trigger:

- **The list** shows every visible lesson under its topic, with what the device says was read.
- **Featured** is the next unread lesson. The default reading order (``path`` in
  ``data/learn/lessons.yaml``) is re-ordered by what the person told Ruko about themselves:
  what they are looking at right now, a recent loss or frequent trading, experience with a
  product (beginner lessons go last for someone already regular at it).
- **Suggest** picks one lesson to offer on a quiet result (no pause, no lessons) or beside a
  glossary answer or a calculation, always about the same subject if one exists.

Everything is deterministic and uses only the device snapshot; nothing is stored and the LLM
is not involved. Lesson text comes from the same human-checked templates as every lesson.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ruko.cards.glossary import get_glossary
from ruko.language.templates import Renderer
from ruko.learn.catalog import LessonCatalog, LessonSpec, get_lesson_catalog
from ruko.learn.select import render_lesson
from ruko.models.common import CalculatorTool, DecisionStage, ProductClass
from ruko.models.profile import Experience, UserProfile
from ruko.models.responses import GlossaryEntry, Lesson, LessonTopic, TopicGroup

FREQUENT_TRADING = frozenset({"6_20", "gt_20"})


@dataclass(frozen=True)
class Focus:
    """What the person is looking at right now; lessons about it are offered first."""

    products: frozenset[ProductClass] = frozenset()
    tools: frozenset[CalculatorTool] = frozenset()
    terms: frozenset[str] = frozenset()
    stages: frozenset[DecisionStage] = frozenset()

    def matches(self, lesson: LessonSpec) -> bool:
        """True if the lesson is about a product, calculator or term in focus."""
        return bool(
            self.products & lesson.about_products
            or self.tools & lesson.about_tools
            or self.terms & lesson.about_terms
            or self.stages & lesson.about_stages
        )


@dataclass
class HubContent:
    """The rendered Learn list."""

    featured: LessonTopic | None
    read_count: int
    total: int
    topics: list[TopicGroup] = field(default_factory=list)
    words: list[GlossaryEntry] = field(default_factory=list)
    unverified_fact_ids: list[str] = field(default_factory=list)


def _visible(catalog: LessonCatalog, show_unverified: bool) -> list[LessonSpec]:
    return [lesson for lesson in catalog.lessons if lesson.visible(show_unverified)]


def _boosted(lesson: LessonSpec, profile: UserProfile) -> bool:
    """True if the person said something that makes this lesson more worth reading now."""
    said = set()
    if profile.recent.post_loss:
        said.add("post_loss")
    if profile.recent.late_night:
        said.add("late_night")
    if profile.recent.trades_this_week in FREQUENT_TRADING:
        said.add("frequent_trading")
    return bool(lesson.boost_when & said)


def _personal(lesson: LessonSpec, profile: UserProfile) -> int:
    """Rank a lesson for this person.

    0 = they already engage with the subject, 1 = neutral, 2 = a beginner lesson for something
    they are already regular at (goes last).
    """
    levels = {profile.experience.get(c) for c in lesson.about_products}
    if lesson.introductory and Experience.REGULAR in levels:
        return 2
    if lesson.about_products and levels & {Experience.SOME, Experience.REGULAR}:
        return 0
    return 1


def rank_key(
    lesson: LessonSpec, profile: UserProfile, focus: Focus, catalog: LessonCatalog
) -> tuple[int, int, int, int]:
    """Sort key for what to read next.

    First what they are looking at, then what they said, then their experience, then the
    default reading order.
    """
    return (
        0 if focus.matches(lesson) else 1,
        0 if _boosted(lesson, profile) else 1,
        _personal(lesson, profile),
        catalog.path_index(lesson),
    )


def lesson_topic(lesson: LessonSpec, renderer: Renderer, seen: set[str]) -> LessonTopic:
    """One lesson as a list item (title, one-line summary, reading time)."""
    return LessonTopic(
        id=lesson.id,
        title=renderer.text(lesson.title_key),
        summary=renderer.text(lesson.summary_key),
        read_seconds=lesson.read_seconds,
        topic=lesson.topic,
        seen=lesson.id in seen,
        safety_critical=lesson.safety_critical,
    )


def _unseen_ranked(
    profile: UserProfile, focus: Focus, catalog: LessonCatalog, show_unverified: bool
) -> list[LessonSpec]:
    seen = set(profile.seen_lesson_ids)
    pool = [lesson for lesson in _visible(catalog, show_unverified) if lesson.id not in seen]
    return sorted(pool, key=lambda lesson: rank_key(lesson, profile, focus, catalog))


def suggest_lesson(
    profile: UserProfile,
    renderer: Renderer,
    *,
    focus: Focus = Focus(),  # noqa: B008 - frozen dataclass, safe as a default
    exclude: frozenset[str] = frozenset(),
    show_unverified: bool = True,
) -> LessonTopic | None:
    """Return one unread lesson worth offering now, or None if everything was read.

    Args:
        profile: Device snapshot (what was read, experience, recent context).
        renderer: Renderer for the user's locale.
        focus: What the person is looking at; lessons about it come first.
        exclude: Lesson IDs already on screen.
        show_unverified: False in production.
    """
    catalog = get_lesson_catalog()
    for lesson in _unseen_ranked(profile, focus, catalog, show_unverified):
        if lesson.id not in exclude:
            return lesson_topic(lesson, renderer, set(profile.seen_lesson_ids))
    return None


def build_hub(
    profile: UserProfile, renderer: Renderer, *, show_unverified: bool = True
) -> HubContent:
    """Build the Learn list for this person."""
    catalog = get_lesson_catalog()
    visible = _visible(catalog, show_unverified)
    seen = set(profile.seen_lesson_ids)
    topics = []
    for topic in catalog.topics:
        lessons = sorted(
            (lesson for lesson in visible if lesson.topic == topic), key=catalog.path_index
        )
        if lessons:
            topics.append(
                TopicGroup(
                    id=topic,
                    title=renderer.text(catalog.topic_title_key(topic)),
                    lessons=[lesson_topic(lesson, renderer, seen) for lesson in lessons],
                )
            )
    return HubContent(
        featured=suggest_lesson(profile, renderer, show_unverified=show_unverified),
        read_count=sum(1 for lesson in visible if lesson.id in seen),
        total=len(visible),
        topics=topics,
        words=[
            GlossaryEntry(
                id=term.id,
                title=renderer.text(term.title_key),
                brief=renderer.text(term.brief_key),
            )
            for term in get_glossary().terms
        ],
    )


def next_after(
    spec: LessonSpec, profile: UserProfile, renderer: Renderer, *, show_unverified: bool = True
) -> LessonTopic | None:
    """The lesson to read after this one.

    The next unread lesson further along the reading path (still re-ordered by what the person
    said about themselves), then any earlier unread one.
    """
    catalog = get_lesson_catalog()
    here = catalog.path_index(spec)
    pool = [
        lesson
        for lesson in _unseen_ranked(profile, Focus(), catalog, show_unverified)
        if lesson.id != spec.id
    ]
    pool.sort(key=lambda lesson: catalog.path_index(lesson) < here)  # stable: keeps the ranking
    if not pool:
        return None
    return lesson_topic(pool[0], renderer, set(profile.seen_lesson_ids))


def build_lesson_page(
    lesson_id: str, profile: UserProfile, renderer: Renderer, *, show_unverified: bool = True
) -> tuple[Lesson, LessonTopic | None, list[str]]:
    """Render one whole lesson plus the lesson to read after it.

    Raises:
        KeyError: Unknown lesson, or one hidden in this environment.
    """
    catalog = get_lesson_catalog()
    spec = catalog.get(lesson_id)
    if spec is None or not spec.visible(show_unverified):
        raise KeyError(lesson_id)
    lesson, unverified = render_lesson(spec, renderer)
    lesson = lesson.model_copy(update={"summary": renderer.text(spec.summary_key)})
    after = next_after(spec, profile, renderer, show_unverified=show_unverified)
    return lesson, after, unverified


def lesson_by_id(
    lesson_id: str | None,
    profile: UserProfile,
    renderer: Renderer,
    *,
    show_unverified: bool = True,
) -> LessonTopic | None:
    """A named lesson as a list item, if it exists, is visible and was not read yet."""
    spec = get_lesson_catalog().get(lesson_id) if lesson_id else None
    if spec is None or not spec.visible(show_unverified) or spec.id in profile.seen_lesson_ids:
        return None
    return lesson_topic(spec, renderer, set(profile.seen_lesson_ids))
