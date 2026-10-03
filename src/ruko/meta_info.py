"""``GET /v1/meta``: what the service supports and how verified its content is.

Lists languages, template counts by status, every displayed fact with its verification
status and ``as_of`` date, policy and prompt versions, and which providers are configured
(true/false only, never keys).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ruko import __version__
from ruko.engine.base_rates import load_base_rates
from ruko.engine.policy import get_intervention_policy
from ruko.facts import regulatory
from ruko.language.detect import language_registry
from ruko.language.speech_codes import speech_code_for
from ruko.language.templates import get_template_store
from ruko.models.common import StrictModel
from ruko.orchestrator.services import Services
from ruko.recovery.guide import recovery_routes
from ruko.understanding.extract import get_prompts


class LanguageInfo(StrictModel):
    """One supported language."""

    code: str = Field(description="Locale code.")
    enabled: bool = Field(description="Enabled in this deployment.")
    voice: bool = Field(description="Has a speech-provider language tag.")
    templates_draft: int = Field(ge=0, description="Templates still in draft.")
    templates_verified: int = Field(ge=0, description="Templates verified by a human.")


class FactStatus(StrictModel):
    """Verification status of one displayed fact."""

    fact_id: str = Field(description="'<file>:<id>'.")
    as_of: str = Field(description="Date the fact is valid as of.")
    verified_by_human: bool = Field(description="Checked by the repo owner.")
    todo_verify: bool = Field(description="Has an open TODO_VERIFY note.")


class MetaResponse(StrictModel):
    """Service capabilities and content verification status."""

    kind: Literal["meta"] = "meta"
    version: str = Field(description="Service version.")
    languages: list[LanguageInfo] = Field(description="Supported languages.")
    facts: list[FactStatus] = Field(description="Every displayed fact.")
    policy_version: str = Field(description="Intervention policy version.")
    prompt_version: str = Field(description="LLM prompt version.")
    providers: dict[str, bool] = Field(description="Which providers are configured.")


def fact_statuses() -> list[FactStatus]:
    """Return the verification status of every fact Ruko can display."""
    statuses: list[FactStatus] = []
    facts, _ = load_base_rates()
    for fact in facts:
        statuses.append(
            FactStatus(
                fact_id=f"base_rates:{fact.id}",
                as_of=fact.as_of,
                verified_by_human=fact.verified_by_human,
                todo_verify=False,
            )
        )
    files = (("regulatory", regulatory()), ("recovery_routes", recovery_routes()))
    for name, entries in files:
        for key, entry in entries.items():
            statuses.append(
                FactStatus(
                    fact_id=f"{name}:{key}",
                    as_of=str(entry["as_of"]),
                    verified_by_human=bool(entry["verified_by_human"]),
                    todo_verify="todo_verify" in entry,
                )
            )
    return statuses


def build_meta_info(services: Services) -> MetaResponse:
    """Assemble the ``/v1/meta`` response."""
    store = get_template_store()
    languages = []
    for spec in language_registry():
        statuses = [store.get(spec.code, key) for key in store.keys(spec.code)]
        languages.append(
            LanguageInfo(
                code=spec.code,
                enabled=spec.code in services.settings.enabled_locales,
                voice=speech_code_for(spec.code) is not None,
                templates_draft=sum(t is not None and t.status == "draft" for t in statuses),
                templates_verified=sum(
                    t is not None and t.status == "human_verified" for t in statuses
                ),
            )
        )
    return MetaResponse(
        version=__version__,
        languages=languages,
        facts=fact_statuses(),
        policy_version=get_intervention_policy().version,
        prompt_version=get_prompts().version,
        providers={
            "llm": services.llm is not None,
            "speech": bool(services.speech.providers),
        },
    )
