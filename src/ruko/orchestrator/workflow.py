"""The analyze workflow: one shared item in, one typed response out, routed by stage.

Steps (each through the policy-checked executor, each in the content-free trace):

1. input adapter: text / link as-is; screenshot -> checked image -> OCR; voice -> STT
2. detect language (local) and pick the response locale
3. input guardrail on the raw text (sensitive data, refusal patterns) -> refusal
4. local PII redaction; only redacted text ever goes to the LLM
5. deterministic understanding (lexicon, link strings, payment placeholders)
6. decision stage (deterministic first; the LLM may only fill an unknown stage)
7. LLM extraction as a helper (or lexicon-only); LLM refusal classes can only add a refusal
8. route by stage:
   - learn            -> curated glossary
   - evaluate_content -> content report (signals only, no verdict, no behavioural engine)
   - already_acted    -> recovery guide (no pause)
   - unknown          -> one question about what the user wants
   - consider_action / about_to_act -> clarify if needed -> engine -> cards -> pause
9. every response passes the output validator (per template, and once more as a whole)

The workflow decides which steps run; it never decides the stage alone, the level, or
any user-facing text.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ruko.cards.glossary import build_glossary
from ruko.engine.engine import decide
from ruko.engine.policy import get_intervention_policy
from ruko.errors import ErrorCode, RukoError
from ruko.guardrails.intent_gate import GateResult, check_intent
from ruko.guardrails.policy import get_policy
from ruko.language.detect import detect_language
from ruko.language.redact import redact
from ruko.language.templates import Renderer
from ruko.models.common import DecisionStage, RefusalClass
from ruko.models.event import DecisionEvent, StageResult
from ruko.models.inputs import InputType, RawInput
from ruko.models.profile import UserProfile
from ruko.models.recovery import RecoveryGuide
from ruko.models.requests import AnalyzeRequest, DecisionAnswers, VoiceAnalyzeRequest
from ruko.models.responses import (
    ClarifyOption,
    ClarifyQuestion,
    ClarifyResponse,
    ContentReportResponse,
    GlossaryResponse,
    PauseResponse,
    RefusalResponse,
    ResponseMeta,
    TemplateRef,
)
from ruko.observability import log_event
from ruko.orchestrator.content_report import build_content_report
from ruko.orchestrator.executor import ToolExecutor
from ruko.orchestrator.pause import build_pause
from ruko.orchestrator.services import Services
from ruko.providers.speech.audio import decode_audio
from ruko.recovery.guide import build_guide
from ruko.understanding.clarify import fields_to_ask, render_questions, with_missing_fields
from ruko.understanding.extract import ExtractionOutcome, extract, second_opinion_from
from ruko.understanding.merge import (
    DeterministicFindings,
    apply_answers,
    collect_deterministic,
    merge,
)
from ruko.understanding.screenshot import decode_image, image_to_text
from ruko.understanding.stage import classify_stage, recovery_answers_from_text

AnalyzeResult = (
    PauseResponse
    | RefusalResponse
    | ClarifyResponse
    | ContentReportResponse
    | GlossaryResponse
    | RecoveryGuide
)
ACTING = frozenset({DecisionStage.CONSIDER_ACTION, DecisionStage.ABOUT_TO_ACT})
"""Stages where the user says they are acting with money: always a financial decision."""
STAGE_OPTIONS = (
    DecisionStage.LEARN,
    DecisionStage.EVALUATE_CONTENT,
    DecisionStage.CONSIDER_ACTION,
    DecisionStage.ALREADY_ACTED,
)


@dataclass
class Context:
    """What every step of one request shares (no message content)."""

    request_id: str
    locale: str
    executor: ToolExecutor
    renderer: Renderer
    outcome: ExtractionOutcome | None = None
    stage: StageResult | None = None
    show_unverified: bool = True

    def meta(
        self, *, unverified_fact_ids: list[str] | None = None, policy_version: str | None = None
    ) -> ResponseMeta:
        """Build response metadata from the context."""
        return build_meta(
            self.request_id,
            self.locale,
            self.executor,
            self.renderer,
            outcome=self.outcome,
            unverified_fact_ids=unverified_fact_ids,
            policy_version=policy_version,
            stage=self.stage,
        )


def build_meta(
    request_id: str,
    locale: str,
    executor: ToolExecutor,
    renderer: Renderer,
    *,
    outcome: ExtractionOutcome | None = None,
    unverified_fact_ids: list[str] | None = None,
    policy_version: str | None = None,
    stage: StageResult | None = None,
) -> ResponseMeta:
    """Collect response metadata (versions, stage, extraction mode, template status, trace)."""
    return ResponseMeta(
        request_id=request_id,
        locale=locale,
        policy_version=policy_version,
        prompt_version=outcome.prompt_version if outcome else None,
        extraction_mode="not_run" if outcome is None else outcome.mode,
        stage=stage.stage if stage else None,
        stage_source=stage.source if stage else None,
        unverified_fact_ids=unverified_fact_ids or [],
        draft_template_count=renderer.draft_count,
        missing_template_keys=list(renderer.missing_keys),
        blocked_output_count=renderer.blocked_count,
        trace=list(executor.trace),
    )


def input_text(raw: RawInput, services: Services, executor: ToolExecutor) -> str:
    """Turn a shared item into text (screenshots go through OCR; nothing is stored)."""
    if raw.type == InputType.IMAGE:
        image = executor.run(
            "decode_image", decode_image, raw.content, services.settings.max_image_bytes
        )
        return executor.run(
            "ocr", image_to_text, image, services.llm, services.settings.max_text_chars
        )
    if raw.type == InputType.VOICE:
        raise RukoError(ErrorCode.INVALID_REQUEST)  # voice uses /v1/analyze/voice
    return raw.content


def _refusal_response(gate: GateResult, ctx: Context) -> RefusalResponse:
    assert gate.refusal_class is not None
    policy = get_policy()
    if gate.refusal_class == RefusalClass.SENSITIVE_DATA_SUBMISSION:
        keys = (policy.sensitive_message_key, policy.sensitive_alternative_key)
    else:
        rule = next(r for r in policy.refusal_rules if r.refusal_class == gate.refusal_class)
        keys = (rule.message_key, rule.alternative_key)
    log_event("analyze_refused", error_code=gate.refusal_class.value)
    return RefusalResponse(
        refusal_class=gate.refusal_class,
        message=ctx.renderer.text(keys[0]),
        alternative=ctx.renderer.text(keys[1]),
        speak=[TemplateRef(key=k) for k in keys],
        meta=ctx.meta(),
    )


def _without_evidence(event: DecisionEvent) -> DecisionEvent:
    """Drop evidence excerpts so no text from the user's message is echoed back."""
    signals = [s.model_copy(update={"evidence": None}) for s in event.signals]
    return event.model_copy(update={"signals": signals})


def _extract(redacted: str, services: Services, ctx: Context) -> ExtractionOutcome:
    outcome = ctx.executor.run(
        "llm_extract",
        extract,
        redacted,
        services.llm,
        invalid_output_retries=services.settings.llm_invalid_output_retries,
    )
    if services.llm is None:
        ctx.executor.note("llm_extract", "skipped")
    elif outcome.mode == "lexicon_only":
        ctx.executor.note("llm_extract", "fallback")
    return outcome


def _looks_financial(findings: DeterministicFindings) -> bool:
    return bool(findings.hints.get("product_class") or findings.signals)


def _llm_stage(stage: StageResult, outcome: ExtractionOutcome) -> StageResult:
    """The LLM may fill an unknown stage, never override a deterministic one."""
    llm = outcome.extraction
    if stage.stage != DecisionStage.UNKNOWN or llm is None or llm.stage is None:
        return stage
    if llm.stage == DecisionStage.UNKNOWN:
        return stage
    return StageResult(stage=llm.stage, confidence=0.5, source="llm")


def _stage_question(event: DecisionEvent, ctx: Context) -> ClarifyResponse:
    question = ClarifyQuestion(
        field="stage",
        text=ctx.renderer.text("stage.question"),
        options=[
            ClarifyOption(value=s.value, label=ctx.renderer.text(f"stage.option.{s.value}"))
            for s in STAGE_OPTIONS
        ],
    )
    return ClarifyResponse(
        questions=[question],
        event=_without_evidence(event),
        speak=[TemplateRef(key="stage.question")],
        meta=ctx.meta(),
    )


def _glossary(text: str, ctx: Context) -> GlossaryResponse:
    content = ctx.executor.run("glossary", build_glossary, text, ctx.renderer, ctx.show_unverified)
    return GlossaryResponse(
        found=content.found,
        term=content.term,
        title=content.title,
        body=content.body,
        sources=content.sources,
        speak=content.speak,
        meta=ctx.meta(unverified_fact_ids=content.unverified_fact_ids),
    )


def _recovery(text: str, findings: DeterministicFindings, ctx: Context) -> RecoveryGuide:
    answers = recovery_answers_from_text(text, findings.payment_destination)
    guide = ctx.executor.run(
        "recovery", build_guide, answers, ctx.renderer, ctx.meta(), ctx.show_unverified
    )
    return guide.model_copy(update={"meta": ctx.meta()})


def _decision_path(
    event: DecisionEvent,
    answers: DecisionAnswers,
    profile: UserProfile,
    gate: GateResult,
    ctx: Context,
) -> PauseResponse | ClarifyResponse:
    policy_version = get_intervention_policy().version
    questions = ctx.executor.run("clarify", fields_to_ask, event, answers)
    if questions:
        return ClarifyResponse(
            questions=render_questions(questions, ctx.renderer),
            event=_without_evidence(event),
            speak=[TemplateRef(key=q.question_key) for q in questions],
            meta=ctx.meta(policy_version=policy_version),
        )
    decision = ctx.executor.run("engine", decide, event, profile)
    ctx.executor.note("engine", "ok", decision.reason_codes)
    content = ctx.executor.run(
        "render",
        build_pause,
        event,
        decision,
        profile,
        ctx.renderer,
        verdict_requested=gate.verdict_requested,
        urgent=event.stage == DecisionStage.ABOUT_TO_ACT,
        show_unverified=ctx.show_unverified,
    )
    log_event("analyze_done", logging.INFO, reason_codes=[c.value for c in decision.reason_codes])
    return content.to_response(
        ctx.meta(unverified_fact_ids=content.unverified_fact_ids, policy_version=policy_version)
    )


def analyze_text(
    text: str,
    *,
    claimed_locale: str | None,
    requested_locale: str | None,
    profile: UserProfile,
    answers: DecisionAnswers,
    services: Services,
    executor: ToolExecutor,
    request_id: str,
) -> AnalyzeResult:
    """Run steps 2-9 on text (typed, OCR'd or transcribed). Never stores or logs it."""
    if len(text) > services.settings.max_text_chars:
        raise RukoError(ErrorCode.PAYLOAD_TOO_LARGE)
    detection = executor.run("detect_language", detect_language, text)
    locale = services.response_locale(requested_locale, claimed_locale or detection.language)
    ctx = Context(request_id, locale, executor, Renderer(locale))
    ctx.show_unverified = services.settings.unverified_facts_visible

    gate = executor.run("intent_gate", check_intent, text)
    if gate.refused:
        return _refusal_response(gate, ctx)

    redacted = executor.run("redact", redact, text).text
    findings = executor.run("deterministic_signals", collect_deterministic, redacted)
    ctx.stage = executor.run(
        "stage",
        classify_stage,
        text,
        declared=answers.stage,
        declared_amount=answers.amount_inr is not None,
        looks_financial=_looks_financial(findings),
    )
    log_event("stage_classified", stage=ctx.stage.stage.value)
    if ctx.stage.stage == DecisionStage.LEARN:
        return _glossary(text, ctx)
    if ctx.stage.stage == DecisionStage.ALREADY_ACTED:
        return _recovery(text, findings, ctx)

    ctx.outcome = _extract(redacted, services, ctx)
    if ctx.outcome.refusal_classes:
        second = executor.run(
            "second_opinion",
            check_intent,
            text,
            second_opinion=second_opinion_from(ctx.outcome),
            second_opinion_text=redacted,
        )
        if second.refused:
            return _refusal_response(second, ctx)
    ctx.stage = _llm_stage(ctx.stage, ctx.outcome)

    understanding = executor.run("merge", merge, findings, ctx.outcome)
    event = apply_answers(understanding.event, answers)
    acting = ctx.stage.stage in ACTING and ctx.stage.source in ("lexicon", "user")
    update = {"stage": ctx.stage.stage, **({"is_financial_decision": True} if acting else {})}
    event = with_missing_fields(
        DecisionEvent.model_validate({**event.model_dump(), **update}), answers
    )
    stage = ctx.stage.stage
    if stage == DecisionStage.LEARN:
        return _glossary(text, ctx)
    if stage == DecisionStage.ALREADY_ACTED:
        return _recovery(text, findings, ctx)
    if stage == DecisionStage.UNKNOWN:
        return _stage_question(event, ctx)
    if stage == DecisionStage.EVALUATE_CONTENT:
        report = executor.run(
            "content_report", build_content_report, event, ctx.renderer, ctx.show_unverified
        )
        return report.to_response(ctx.meta(unverified_fact_ids=report.unverified_fact_ids))
    return _decision_path(event, answers, profile, gate, ctx)


def analyze(request: AnalyzeRequest, services: Services, request_id: str) -> AnalyzeResult:
    """``POST /v1/analyze``: text, link or screenshot."""
    executor = ToolExecutor()
    text = input_text(request.input, services, executor)
    return analyze_text(
        text,
        claimed_locale=request.input.claimed_locale,
        requested_locale=request.locale,
        profile=request.profile,
        answers=request.answers,
        services=services,
        executor=executor,
        request_id=request_id,
    )


def analyze_voice(
    request: VoiceAnalyzeRequest, services: Services, request_id: str
) -> AnalyzeResult:
    """``POST /v1/analyze/voice``: check audio, transcribe in memory, then analyze."""
    settings = services.settings
    executor = ToolExecutor()
    if request.locale is not None:
        services.response_locale(request.locale)  # fail fast before any provider call
    clip = executor.run(
        "decode_audio",
        decode_audio,
        request.audio_base64,
        request.audio_format,
        settings.max_audio_bytes,
        settings.max_audio_seconds,
    )
    transcript = executor.run("stt", services.speech.transcribe, clip, request.speech_locale)
    return analyze_text(
        transcript.text[: settings.max_text_chars],
        claimed_locale=transcript.locale or request.speech_locale,
        requested_locale=request.locale,
        profile=request.profile,
        answers=request.answers,
        services=services,
        executor=executor,
        request_id=request_id,
    )
