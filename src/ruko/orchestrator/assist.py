"""The smaller workflows: speak, cards, recover, journal review, broker order-intent.

Each runs its steps through the policy-checked executor and returns a typed response.
"""

from __future__ import annotations

import base64
import datetime as dt

from ruko.cards.select import select_cards
from ruko.engine.engine import decide
from ruko.engine.policy import get_intervention_policy
from ruko.errors import ErrorCode, RukoError
from ruko.journal.review import build_review
from ruko.language.speak import build_speech_text
from ruko.language.templates import Renderer
from ruko.learn.catalog import get_lesson_catalog
from ruko.learn.hub import Focus, build_hub, build_lesson_page, suggest_lesson
from ruko.learn.select import explain_calculation, speak_refs_for_lesson
from ruko.models.calculation import CalculationResponse
from ruko.models.common import (
    Certainty,
    DecisionStage,
    FundingSource,
    InterventionLevel,
    ReasonCode,
    SignalSource,
)
from ruko.models.event import DecisionEvent, DecisionPlan, Signal
from ruko.models.journal import JournalReviewResponse
from ruko.models.recovery import RecoveryGuide
from ruko.models.requests import (
    CalculateRequest,
    CardsRequest,
    CardsResponse,
    JournalReviewRequest,
    LearnRequest,
    LessonRequest,
    OrderIntentRequest,
    OrderIntentResponse,
    RecoverRequest,
    SpeakRequest,
    SpeakResponse,
)
from ruko.models.responses import ClarifyResponse, LearnHubResponse, LessonResponse
from ruko.orchestrator.executor import ToolExecutor
from ruko.orchestrator.services import Services
from ruko.orchestrator.workflow import build_meta
from ruko.recovery.guide import build_guide, recovery_routes
from ruko.tools.calculate import build_calculation, clarify_questions, missing_fields


def speak(request: SpeakRequest, services: Services, request_id: str) -> SpeakResponse:
    """``POST /v1/speak``: re-render Ruko's own templates (or one lesson), filter, then TTS."""
    locale = services.response_locale(request.locale)
    executor = ToolExecutor()
    renderer = Renderer(locale)
    items = list(request.items)
    if request.lesson_id:
        try:
            items = speak_refs_for_lesson(
                request.lesson_id, show_unverified=services.settings.unverified_facts_visible
            )
        except KeyError:
            raise RukoError(ErrorCode.INVALID_REQUEST) from None
    speech = executor.run(
        "render",
        build_speech_text,
        items,
        renderer,
        services.settings.sarvam_tts_max_chars,
    )
    audio = executor.run("tts", services.speech.synthesize, speech.text, locale)
    return SpeakResponse(
        audio_base64=base64.b64encode(audio.data).decode("ascii"),
        audio_format=audio.format,
        provider=audio.provider,
        meta=build_meta(request_id, locale, executor, renderer),
    )


def calculate(
    request: CalculateRequest, services: Services, request_id: str
) -> CalculationResponse | ClarifyResponse:
    """``POST /v1/calculate``: arithmetic for the user's own numbers (no message, no LLM).

    A missing required number returns a ``clarify`` question, exactly like the text path, so
    an app can drive a live calculator and a typed question with the same code.
    """
    locale = services.response_locale(request.locale)
    executor = ToolExecutor()
    renderer = Renderer(locale)
    inputs = request.inputs
    missing = executor.run("calculate_inputs", missing_fields, inputs)
    if missing:
        questions, refs = clarify_questions(missing, renderer)
        event = DecisionEvent(stage=DecisionStage.CALCULATE, is_financial_decision=False)
        return ClarifyResponse(
            questions=questions,
            event=event,
            speak=refs,
            meta=build_meta(request_id, locale, executor, renderer),
        )
    content = executor.run("calculate", build_calculation, inputs, renderer)
    explained = executor.run(
        "lessons",
        explain_calculation,
        inputs,
        request.profile,
        renderer,
        show_unverified=services.settings.unverified_facts_visible,
    )
    return CalculationResponse(
        tool=content.tool,
        inputs=content.inputs,
        headline=content.headline,
        explanation=content.explanation,
        assumptions=content.assumptions,
        scenarios=content.scenarios,
        lessons=explained.lessons,
        learn_next=None
        if explained.lessons
        else suggest_lesson(
            request.profile,
            renderer,
            focus=Focus(tools=frozenset({inputs.tool} if inputs.tool else ())),
            show_unverified=services.settings.unverified_facts_visible,
        ),
        speak=content.speak,
        meta=build_meta(
            request_id,
            locale,
            executor,
            renderer,
            unverified_fact_ids=explained.unverified_fact_ids,
        ),
    )


def learn_hub(request: LearnRequest, services: Services, request_id: str) -> LearnHubResponse:
    """``POST /v1/learn``: the Learn list, always available, ordered for this person."""
    locale = services.response_locale(request.locale)
    executor = ToolExecutor()
    renderer = Renderer(locale)
    hub = executor.run(
        "learn_hub",
        build_hub,
        request.profile,
        renderer,
        show_unverified=services.settings.unverified_facts_visible,
    )
    return LearnHubResponse(
        featured=hub.featured,
        read_count=hub.read_count,
        total=hub.total,
        topics=hub.topics,
        words=hub.words,
        meta=build_meta(request_id, locale, executor, renderer),
    )


def learn_lesson(request: LessonRequest, services: Services, request_id: str) -> LessonResponse:
    """``POST /v1/learn/lesson``: one whole lesson with tappable terms and what to read next."""
    locale = services.response_locale(request.locale)
    executor = ToolExecutor()
    renderer = Renderer(locale)
    spec = get_lesson_catalog().get(request.lesson_id)
    if spec is None or not spec.visible(services.settings.unverified_facts_visible):
        raise RukoError(ErrorCode.INVALID_REQUEST)
    lesson, after, unverified = executor.run(
        "learn_lesson",
        build_lesson_page,
        request.lesson_id,
        request.profile,
        renderer,
        show_unverified=services.settings.unverified_facts_visible,
    )
    return LessonResponse(
        lesson=lesson,
        next=after,
        meta=build_meta(request_id, locale, executor, renderer, unverified_fact_ids=unverified),
    )


def cards(request: CardsRequest, services: Services, request_id: str) -> CardsResponse:
    """``POST /v1/cards``: cards for an event and profile, at any level (explicit request)."""
    locale = services.response_locale(request.locale)
    executor = ToolExecutor()
    renderer = Renderer(locale)
    decision = executor.run("engine", decide, request.event, request.profile)
    selection = executor.run(
        "cards",
        select_cards,
        request.event,
        decision,
        request.profile,
        renderer,
        min_level=InterventionLevel.L0,
        show_unverified=services.settings.unverified_facts_visible,
    )
    meta = build_meta(
        request_id,
        locale,
        executor,
        renderer,
        unverified_fact_ids=selection.unverified_fact_ids,
        policy_version=decision.policy_version,
    )
    return CardsResponse(cards=selection.cards, meta=meta)


def recover(request: RecoverRequest, services: Services, request_id: str) -> RecoveryGuide:
    """``POST /v1/recover``: the recovery guide for the user's answers."""
    locale = services.response_locale(request.locale)
    executor = ToolExecutor()
    renderer = Renderer(locale)
    placeholder = build_meta(request_id, locale, executor, renderer)
    guide = executor.run(
        "recovery",
        build_guide,
        request.answers,
        renderer,
        placeholder,
        services.settings.unverified_facts_visible,
    )
    routes = recovery_routes()
    unverified = [
        f"recovery_routes:{step.route_id}"
        for step in guide.steps
        if step.route_id and not routes[step.route_id]["verified_by_human"]
    ]
    meta = build_meta(request_id, locale, executor, renderer, unverified_fact_ids=unverified)
    return guide.model_copy(update={"meta": meta})


def journal_review(
    request: JournalReviewRequest, services: Services, request_id: str
) -> JournalReviewResponse:
    """``POST /v1/journal/review``: the user's own patterns; nothing is kept."""
    locale = services.response_locale(request.locale)
    executor = ToolExecutor()
    renderer = Renderer(locale)
    as_of = request.as_of or dt.date.today()
    placeholder = build_meta(request_id, locale, executor, renderer)
    review = executor.run(
        "journal_review", build_review, list(request.entries), as_of, renderer, placeholder
    )
    return review.model_copy(update={"meta": build_meta(request_id, locale, executor, renderer)})


def order_intent_event(request: OrderIntentRequest) -> DecisionEvent:
    """Build the decision event for a broker's order intent (no instrument, no user ID).

    Rule checks use the upper bound of the amount band. A ``leveraged`` order (e.g. margin)
    adds ``LEVERAGED_PRODUCT`` even when the product class itself is not a derivative.
    ``plan_matched`` means the order follows a plan the user logged, so no plan reason.
    """
    signals = []
    if request.leveraged:
        signals.append(
            Signal(
                code=ReasonCode.LEVERAGED_PRODUCT,
                certainty=Certainty.LIKELY,
                source=SignalSource.USER,
            )
        )
    return DecisionEvent(
        is_financial_decision=True,
        product_class=request.product_class,
        amount_inr=request.amount_band.max_inr,
        funding_source=FundingSource.BORROWED if request.borrowed_funds else FundingSource.UNKNOWN,
        plan=DecisionPlan(matches_prior_plan=True) if request.plan_matched else None,
        signals=signals,
    )


def order_intent(request: OrderIntentRequest, services: Services) -> OrderIntentResponse:
    """``POST /v1/order-intent``: level and reason codes only. No text, no advice."""
    executor = ToolExecutor()
    decision = executor.run("engine", decide, order_intent_event(request), request.profile)
    return OrderIntentResponse(
        level=decision.level,
        reason_codes=decision.reason_codes,
        policy_version=get_intervention_policy().version,
    )
