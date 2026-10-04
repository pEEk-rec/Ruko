"""The calculator and lessons evaluation split as a regression test.

The designed behaviour must keep holding.

Runs every item of ``eval/datasets/phase2.yaml`` through the real workflow (LLM off) with the
same harness the report uses, and checks calculation routing, that product and prediction
phrasings stay refused, lesson selection exactly as designed, and the caps.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

from ruko.config import Settings
from ruko.orchestrator.services import Services
from ruko.providers.speech.factory import SpeechChain

ROOT = Path(__file__).resolve().parents[2]


def _load_harness():
    spec = importlib.util.spec_from_file_location("run_eval", ROOT / "eval" / "run_eval.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_eval"] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


HARNESS = _load_harness()
ITEMS = HARNESS.load_items("phase2")
SERVICES = Services(
    Settings(environment="test", llm_provider="none", speech_providers=[]), None, SpeechChain([])
)


@pytest.mark.parametrize("item", ITEMS, ids=[i["id"] for i in ITEMS])
def test_phase2_item(item):
    result = HARNESS.run_item(item, "phase2", SERVICES)
    expect = item["expect"]
    assert result.kind == expect["kind"], (item["text"], result.kind)
    if "stage" in expect:
        assert result.stage == expect["stage"], item["text"]
    if "tool" in expect:
        assert result.tool == expect["tool"], item["text"]
    if "lessons" in expect:
        assert set(result.lessons) == set(expect["lessons"]), item["text"]
    assert len(result.lessons) <= 2
    assert len(result.lessons) + len(result.cards) <= 3
    assert not result.violations
    assert result.blocked == 0


def test_dataset_covers_all_three_languages_and_both_directions():
    langs = {i["lang"] for i in ITEMS}
    assert {"en", "hi", "kn"} <= langs
    kinds = {i["expect"]["kind"] for i in ITEMS}
    assert {"calculation", "clarify", "refusal", "glossary", "pause", "content_report"} <= kinds
