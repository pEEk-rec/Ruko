"""LLM extraction: redacted text in, validated structured fields out.

Steps:

1. Wrap the **redacted** text between fixed markers (marker strings inside the text are
   removed, so the message cannot close the data block early). The system prompt says the
   message is data, not instructions.
2. Ask the provider for JSON; validate it with Pydantic (``LLMExtraction``).
3. On invalid output, retry with the validation errors (field locations and messages).
4. Clean the result with deterministic policy: only allowed signal codes, evidence must be
   an exact quote of the text (else the signal is dropped), the LLM can never say
   ``broker_or_exchange`` and can never raise the sensitive-data refusal.
5. If the provider fails or every attempt is invalid, return a ``lexicon_only`` outcome:
   the rest of the pipeline still works without the LLM.

The LLM never sees or returns amounts or funding sources; the schema has no such fields.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ruko.data_files import load_yaml
from ruko.errors import ErrorCode
from ruko.guardrails.intent_gate import SecondOpinion
from ruko.guardrails.normalize import normalize
from ruko.models.common import (
    Certainty,
    EvidenceSpan,
    HoldingIntent,
    PaymentDestination,
    ProductClass,
    ReasonCode,
    RefusalClass,
    SignalSource,
    SourceType,
)
from ruko.models.event import Signal
from ruko.providers.llm.base import LLMError, LLMProvider, LLMRequest, Message

ExtractedField = Literal["product_class", "source_type", "holding_intent", "payment_destination"]
ExtractionMode = Literal["llm", "lexicon_only"]
_CODE_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
_CERTAINTY_STRENGTH = {Certainty.LIKELY: 2, Certainty.POSSIBLE: 1, Certainty.UNCLEAR: 0}


@dataclass(frozen=True)
class Prompts:
    """The versioned prompt file (``data/prompts/extraction.yaml``)."""

    version: str
    allowed_codes: frozenset[ReasonCode]
    start_marker: str
    end_marker: str
    system: str
    user: str
    retry: str
    ocr_system: str
    ocr_user: str


@lru_cache(maxsize=1)
def get_prompts() -> Prompts:
    """Load the prompt file (cached)."""
    raw = load_yaml("prompts", "extraction.yaml")
    return Prompts(
        version=str(raw["version"]),
        allowed_codes=frozenset(ReasonCode(c) for c in raw["allowed_signal_codes"]),
        start_marker=raw["markers"]["start"],
        end_marker=raw["markers"]["end"],
        system=raw["extraction"]["system"],
        user=raw["extraction"]["user"],
        retry=raw["extraction"]["retry"],
        ocr_system=raw["ocr"]["system"],
        ocr_user=raw["ocr"]["user"],
    )


class LLMSignal(BaseModel):
    """A signal as the LLM proposes it (before evidence checking)."""

    code: ReasonCode
    evidence: str = Field(min_length=1, max_length=400)
    certainty: Certainty


class LLMExtraction(BaseModel):
    """The JSON the LLM must return. Unknown keys (e.g. an amount) are ignored."""

    model_config = ConfigDict(extra="ignore")

    is_financial_decision: bool
    product_class: ProductClass = ProductClass.UNKNOWN
    source_type: SourceType = SourceType.UNKNOWN
    holding_intent: HoldingIntent = HoldingIntent.UNKNOWN
    payment_destination: PaymentDestination = PaymentDestination.UNKNOWN
    field_confidence: dict[ExtractedField, Certainty] = Field(default_factory=dict)
    signals: list[LLMSignal] = Field(default_factory=list, max_length=20)
    request_classes: list[RefusalClass] = Field(default_factory=list, max_length=6)


@dataclass(frozen=True)
class ExtractionOutcome:
    """Result of extraction. Holds structured fields only, never free text for users.

    Attributes:
        mode: ``llm`` if a valid LLM answer was used, otherwise ``lexicon_only``.
        extraction: The cleaned LLM fields (None in lexicon-only mode).
        signals: LLM-proposed signals whose evidence was found in the text.
        refusal_classes: Refusal classes the LLM saw in the user's own request.
        prompt_version: Prompt version used (None if no LLM call was made).
        attempts: Number of provider calls made.
        fallback_reason: Why the LLM result was not used (None if used or not configured).
        dropped_signals: LLM signals removed (disallowed code or evidence not in the text).
    """

    mode: ExtractionMode
    extraction: LLMExtraction | None = None
    signals: tuple[Signal, ...] = ()
    refusal_classes: tuple[RefusalClass, ...] = ()
    prompt_version: str | None = None
    attempts: int = 0
    fallback_reason: ErrorCode | None = None
    dropped_signals: int = 0


def fence_message(text: str, prompts: Prompts) -> str:
    """Put the message between the markers, removing any marker text inside it."""
    for marker in (prompts.start_marker, prompts.end_marker):
        text = text.replace(marker, " ")
    return f"{prompts.start_marker}\n{text}\n{prompts.end_marker}"


def build_extraction_request(redacted_text: str, prompts: Prompts | None = None) -> LLMRequest:
    """Build the first extraction request for already-redacted text."""
    prompts = prompts or get_prompts()
    user = prompts.user.replace("{message}", fence_message(redacted_text, prompts))
    return LLMRequest(system=prompts.system, messages=(Message(role="user", text=user),))


def parse_extraction(raw: str) -> LLMExtraction:
    """Parse and validate the model's JSON reply.

    Raises:
        ValueError: If the reply is not JSON or does not match the schema.
    """
    try:
        data = json.loads(_CODE_FENCE.sub("", raw))
    except json.JSONDecodeError as error:
        raise ValueError(f"not valid JSON ({error.msg})") from None
    return LLMExtraction.model_validate(data)


def describe_errors(error: Exception) -> str:
    """Summarize why a reply was rejected, as field locations and messages only."""
    if isinstance(error, ValidationError):
        items = [
            f"{'.'.join(str(p) for p in e['loc']) or 'root'}: {e['msg']}"
            for e in error.errors(include_input=False, include_url=False)
        ]
        return "; ".join(items[:8])
    return str(error)[:200]


def _find_evidence(quote: str, normalized_text: str) -> EvidenceSpan | None:
    needle = normalize(quote)
    start = normalized_text.find(needle) if needle else -1
    if start < 0:
        return None
    return EvidenceSpan(start=start, end=start + len(needle), text=needle[:200])


def clean_signals(
    proposed: list[LLMSignal], redacted_text: str, prompts: Prompts
) -> tuple[list[Signal], int]:
    """Keep allowed codes whose evidence is an exact quote; one signal per code.

    Returns:
        The kept signals (source ``llm``) and how many proposals were dropped.
    """
    normalized = normalize(redacted_text)
    kept: dict[ReasonCode, Signal] = {}
    dropped = 0
    for item in proposed:
        evidence = _find_evidence(item.evidence, normalized)
        if item.code not in prompts.allowed_codes or evidence is None:
            dropped += 1
            continue
        current = kept.get(item.code)
        if current is None or (
            _CERTAINTY_STRENGTH[item.certainty] > _CERTAINTY_STRENGTH[current.certainty]
        ):
            kept[item.code] = Signal(
                code=item.code, certainty=item.certainty, source=SignalSource.LLM, evidence=evidence
            )
    return list(kept.values()), dropped


def _clean_fields(extraction: LLMExtraction) -> LLMExtraction:
    """Apply policy limits the schema alone does not express."""
    destination = extraction.payment_destination
    if destination == PaymentDestination.BROKER_OR_EXCHANGE:
        destination = PaymentDestination.UNKNOWN  # only the user can declare a broker
    return extraction.model_copy(
        update={
            "payment_destination": destination,
            "signals": [],
            "request_classes": [
                r for r in extraction.request_classes
                if r != RefusalClass.SENSITIVE_DATA_SUBMISSION
            ],
        }
    )  # fmt: skip


def _accept(
    extraction: LLMExtraction, redacted_text: str, prompts: Prompts, attempts: int
) -> ExtractionOutcome:
    signals, dropped = clean_signals(extraction.signals, redacted_text, prompts)
    cleaned = _clean_fields(extraction)
    refusals = tuple(dict.fromkeys(cleaned.request_classes))
    return ExtractionOutcome(
        mode="llm",
        extraction=cleaned,
        signals=tuple(signals),
        refusal_classes=refusals,
        prompt_version=prompts.version,
        attempts=attempts,
        dropped_signals=dropped,
    )


def extract(
    redacted_text: str,
    provider: LLMProvider | None,
    *,
    invalid_output_retries: int = 1,
    prompts: Prompts | None = None,
) -> ExtractionOutcome:
    """Extract structured fields from redacted text, falling back to the lexicon.

    Args:
        redacted_text: Output of ``language.redact.redact()``; never the raw message.
        provider: The LLM provider, or None for lexicon-only extraction.
        invalid_output_retries: Extra attempts after a reply that fails validation.
        prompts: Optional prompt override (defaults to the data file).

    Returns:
        An ``ExtractionOutcome``. Never raises for provider or validation failures.
    """
    if provider is None or not redacted_text.strip():
        return ExtractionOutcome(mode="lexicon_only")
    prompts = prompts or get_prompts()
    request = build_extraction_request(redacted_text, prompts)
    attempts = 0
    for _ in range(invalid_output_retries + 1):
        attempts += 1
        try:
            reply = provider.generate(request)
        except LLMError as error:
            return ExtractionOutcome(
                mode="lexicon_only",
                prompt_version=prompts.version,
                attempts=attempts,
                fallback_reason=error.code,
            )
        try:
            return _accept(parse_extraction(reply), redacted_text, prompts, attempts)
        except (ValueError, ValidationError) as error:
            retry_text = prompts.retry.replace("{errors}", describe_errors(error))
            request = LLMRequest(
                system=request.system,
                messages=request.messages
                + (Message(role="model", text=reply[:4000]), Message(role="user", text=retry_text)),
            )
    return ExtractionOutcome(
        mode="lexicon_only",
        prompt_version=prompts.version,
        attempts=attempts,
        fallback_reason=ErrorCode.LLM_INVALID_OUTPUT,
    )


def second_opinion_from(outcome: ExtractionOutcome) -> SecondOpinion:
    """Adapt the LLM's refusal classes for ``intent_gate.check_intent(second_opinion=...)``.

    The gate lets a second opinion add refusals, never remove them.
    """
    classes = outcome.refusal_classes
    return lambda _text: classes
