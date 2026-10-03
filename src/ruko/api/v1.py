"""The versioned API (``/v1``). Each route validates its body, then calls one workflow.

Routes are plain (sync) functions; FastAPI runs them in a worker thread. Bodies are never
logged; responses carry ``meta`` with a content-free trace. Every text response passes the
assertion-level validator once more as a whole (``ensure_safe``) before it leaves.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Request
from pydantic import Field

from ruko.guardrails.output_validator import ensure_safe
from ruko.meta_info import MetaResponse, build_meta_info
from ruko.models.journal import JournalReviewResponse
from ruko.models.recovery import RecoveryGuide
from ruko.models.requests import (
    AnalyzeRequest,
    CardsRequest,
    CardsResponse,
    JournalReviewRequest,
    OrderIntentRequest,
    OrderIntentResponse,
    RecoverRequest,
    SpeakRequest,
    SpeakResponse,
    VoiceAnalyzeRequest,
)
from ruko.models.responses import (
    ClarifyResponse,
    ContentReportResponse,
    GlossaryResponse,
    PauseResponse,
    RefusalResponse,
)
from ruko.observability import current_request_id
from ruko.orchestrator import assist, workflow
from ruko.orchestrator.services import Services

router = APIRouter(prefix="/v1")

AnalyzeResponse = Annotated[
    PauseResponse
    | RefusalResponse
    | ClarifyResponse
    | ContentReportResponse
    | GlossaryResponse
    | RecoveryGuide,
    Field(discriminator="kind"),
]


def _services(request: Request) -> Services:
    return request.app.state.services


@router.post("/analyze", response_model=AnalyzeResponse, tags=["analyze"])
def analyze(body: AnalyzeRequest, request: Request) -> workflow.AnalyzeResult:
    """Analyze a shared text, link or screenshot, routed by decision stage.

    Returns a pause, refusal, clarifying question, content report, glossary entry or
    recovery guide.
    """
    return ensure_safe(workflow.analyze(body, _services(request), current_request_id()))


@router.post("/analyze/voice", response_model=AnalyzeResponse, tags=["analyze"])
def analyze_voice(body: VoiceAnalyzeRequest, request: Request) -> workflow.AnalyzeResult:
    """Analyze a voice note (transcribed in memory, never stored)."""
    return ensure_safe(workflow.analyze_voice(body, _services(request), current_request_id()))


@router.post("/speak", response_model=SpeakResponse, tags=["speech"])
def speak(body: SpeakRequest, request: Request) -> SpeakResponse:
    """Read Ruko's own templates aloud (re-rendered and filtered; no free text)."""
    return ensure_safe(assist.speak(body, _services(request), current_request_id()))


@router.post("/cards", response_model=CardsResponse, tags=["cards"])
def cards(body: CardsRequest, request: Request) -> CardsResponse:
    """Just-in-time explanation cards for an event and profile (max 3)."""
    return ensure_safe(assist.cards(body, _services(request), current_request_id()))


@router.post("/recover", response_model=RecoveryGuide, tags=["recovery"])
def recover(body: RecoverRequest, request: Request) -> RecoveryGuide:
    """Recovery guide: urgent steps first, evidence checklist, draft complaint."""
    return ensure_safe(assist.recover(body, _services(request), current_request_id()))


@router.post("/journal/review", response_model=JournalReviewResponse, tags=["journal"])
def journal_review(body: JournalReviewRequest, request: Request) -> JournalReviewResponse:
    """The user's own patterns from their device journal (nothing is stored)."""
    return ensure_safe(assist.journal_review(body, _services(request), current_request_id()))


@router.post("/order-intent", response_model=OrderIntentResponse, tags=["broker"])
def order_intent(body: OrderIntentRequest, request: Request) -> OrderIntentResponse:
    """Broker embedding: level and reason codes only. No instrument, no user ID, no text."""
    return assist.order_intent(body, _services(request))


@router.get("/meta", response_model=MetaResponse, tags=["meta"])
def meta(request: Request) -> MetaResponse:
    """Languages, template status, fact verification status, versions, providers."""
    return build_meta_info(_services(request))
