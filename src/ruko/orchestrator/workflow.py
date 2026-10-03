"""The analyze workflow: one shared item in, a pause, refusal or clarify response out.

Steps (each through the policy-checked executor, each in the content-free trace):

1. input adapter: text / link as-is; screenshot -> checked image -> OCR; voice -> STT
2. detect language (local) and pick the response locale
3. intent gate on the raw text (sensitive data, refusal patterns) -> refusal
4. local PII redaction; only redacted text goes to the LLM
5. LLM extraction (or lexicon-only fallback); LLM refusal classes can only add a refusal
6. deterministic signals (lexicon, link strings, payment placeholders), merge, user answers
7. clarify: if needed fields are missing, return questions instead of a decision
8. deterministic engine -> level and reasons; cards; render; output filter

The workflow decides which steps run; it never decides the level (step 8 does).
"""

from __future__ import annotations

import logging

from ruko.engine.engine import decide
from ruko.engine.policy import get_intervention_policy
from ruko.errors import ErrorCode, RukoError
from ruko.guardrails.intent_gate import GateResult, check_intent
from ruko.guardrails.policy import get_policy
from ruko.language.detect import detect_language
from ruko.language.redact import redact
from ruko.language.templates import Renderer
from ruko.models.common import RefusalClass
from ruko.models.event import DecisionEvent
from ruko.models.inputs import InputType, RawInput
from ruko.models.profile import UserProfile
from ruko.models.requests import AnalyzeRequest, DecisionAnswers, VoiceAnalyzeRequest
from ruko.models.responses import (
    ClarifyResponse,
    PauseResponse,
    RefusalResponse,
    ResponseMeta,
    TemplateRef,
)
from ruko.observability import log_event
from ruko.orchestrator.executor import ToolExecutor
from ruko.orchestrator.pause import build_pause
from ruko.orchestrator.services import Services
from ruko.providers.speech.audio import decode_audio
from ruko.understanding.clarify import fields_to_ask, render_questions, with_missing_fields
from ruko.understanding.extract import ExtractionOutcome, extract, second_opinion_from
from ruko.understanding.merge import apply_answers, collect_deterministic, merge
from ruko.understanding.screenshot import decode_image, image_to_text

AnalyzeResult = PauseResponse | RefusalResponse | ClarifyResponse


def build_meta(
    request_id: str,
    locale: str,
    executor: ToolExecutor,
    renderer: Renderer,
    *,
    outcome: ExtractionOutcome | None = None,
    unverified_fact_ids: list[str] | None = None,
    policy_version: str | None = None,
) -> ResponseMeta:
    """Collect response metadata (versions, extraction mode, template status, trace)."""
    mode = "not_run" if outcome is None else outcome.mode
    return ResponseMeta(
        request_id=request_id,
        locale=locale,
        policy_version=policy_version,
        prompt_version=outcome.prompt_version if outcome else None,
        extraction_mode=mode,
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


def _refusal(refusal_class: RefusalClass, renderer: Renderer) -> tuple[str, str, list[TemplateRef]]:
    policy = get_policy()
    if refusal_class == RefusalClass.SENSITIVE_DATA_SUBMISSION:
        keys = (policy.sensitive_message_key, policy.sensitive_alternative_key)
    else:
        rule = next(r for r in policy.refusal_rules if r.refusal_class == refusal_class)
        keys = (rule.message_key, rule.alternative_key)
    return renderer.text(keys[0]), renderer.text(keys[1]), [TemplateRef(key=k) for k in keys]


def _refusal_response(gate: GateResult, renderer: Renderer, meta: ResponseMeta) -> RefusalResponse:
    assert gate.refusal_class is not None
    message, alternative, speak = _refusal(gate.refusal_class, renderer)
    log_event("analyze_refused", error_code=gate.refusal_class.value)
    return RefusalResponse(
        refusal_class=gate.refusal_class,
        message=message,
        alternative=alternative,
        speak=speak,
        meta=meta,
    )


def _without_evidence(event: DecisionEvent) -> DecisionEvent:
    """Drop evidence excerpts so no text from the user's message is echoed back."""
    signals = [s.model_copy(update={"evidence": None}) for s in event.signals]
    return event.model_copy(update={"signals": signals})


def _extract(redacted: str, services: Services, executor: ToolExecutor) -> ExtractionOutcome:
    outcome = executor.run(
        "llm_extract",
        extract,
        redacted,
        services.llm,
        invalid_output_retries=services.settings.llm_invalid_output_retries,
    )
    if services.llm is None:
        executor.note("llm_extract", "skipped")
    elif outcome.mode == "lexicon_only":
        executor.note("llm_extract", "fallback")
    return outcome


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
    """Run steps 2-8 on text (typed, OCR'd or transcribed). Never stores or logs it."""
    if len(text) > services.settings.max_text_chars:
        raise RukoError(ErrorCode.PAYLOAD_TOO_LARGE)
    detection = executor.run("detect_language", detect_language, text)
    locale = services.response_locale(requested_locale, claimed_locale or detection.language)
    renderer = Renderer(locale)

    gate = executor.run("intent_gate", check_intent, text)
    if gate.refused:
        return _refusal_response(gate, renderer, build_meta(request_id, locale, executor, renderer))

    redacted = executor.run("redact", redact, text).text
    outcome = _extract(redacted, services, executor)
    if outcome.refusal_classes:
        second = executor.run(
            "second_opinion",
            check_intent,
            text,
            second_opinion=second_opinion_from(outcome),
            second_opinion_text=redacted,
        )
        if second.refused:
            meta = build_meta(request_id, locale, executor, renderer, outcome=outcome)
            return _refusal_response(second, renderer, meta)

    findings = executor.run("deterministic_signals", collect_deterministic, redacted)
    understanding = executor.run("merge", merge, findings, outcome)
    event = with_missing_fields(apply_answers(understanding.event, answers), answers)
    questions = executor.run("clarify", fields_to_ask, event, answers)
    policy_version = get_intervention_policy().version
    if questions:
        rendered = render_questions(questions, renderer)
        speak = [TemplateRef(key=q.question_key) for q in questions]
        meta = build_meta(
            request_id, locale, executor, renderer, outcome=outcome, policy_version=policy_version
        )
        return ClarifyResponse(
            questions=rendered, event=_without_evidence(event), speak=speak, meta=meta
        )

    decision = executor.run("engine", decide, event, profile)
    executor.note("engine", "ok", decision.reason_codes)
    content = executor.run(
        "render",
        build_pause,
        event,
        decision,
        profile,
        renderer,
        verdict_requested=gate.verdict_requested,
    )
    log_event("analyze_done", logging.INFO, reason_codes=[c.value for c in decision.reason_codes])
    meta = build_meta(
        request_id,
        locale,
        executor,
        renderer,
        outcome=outcome,
        unverified_fact_ids=content.unverified_fact_ids,
        policy_version=policy_version,
    )
    return content.to_response(meta)


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
