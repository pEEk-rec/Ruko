"""Ruko evaluation harness: runs both dataset splits and writes the report.

Usage::

    .venv/Scripts/python eval/run_eval.py              # offline: deterministic + lexicon only
    .venv/Scripts/python eval/run_eval.py --live       # also with Gemini (needs a key; slow on
                                                       # the free tier: about 13 s per message)

Splits:

- ``dev`` (eval/datasets/messages.yaml): each message is analyzed as a declared decision
  (Rs 5,000 from savings, empty profile), so the engine path runs; measures signals,
  levels, guardrails and extraction.
- ``heldout`` (eval/datasets/heldout.yaml): written before the guardrail and stage fixes,
  run with NO answers, so routing by decision stage is measured end to end.
- ``phase2`` (eval/datasets/phase2.yaml): calculation routing, prompts that must still be
  refused, and lesson selection. Items may carry their own ``answers`` and ``profile``. Written
  from the design before the first run; same author as the patterns, so not a blind set.

The real workflow runs in-process (no HTTP, nothing stored). Results are reported as they
are; the datasets are never edited to fit them.
"""

from __future__ import annotations

import argparse
import datetime as dt
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ruko.config import Settings, load_settings  # noqa: E402
from ruko.guardrails.output_validator import response_violations  # noqa: E402
from ruko.language.redact import redact  # noqa: E402
from ruko.models.common import CONTENT_CODES  # noqa: E402
from ruko.models.profile import UserProfile  # noqa: E402
from ruko.models.requests import DecisionAnswers  # noqa: E402
from ruko.orchestrator.executor import ToolExecutor  # noqa: E402
from ruko.orchestrator.services import Services  # noqa: E402
from ruko.orchestrator.workflow import analyze_text  # noqa: E402
from ruko.providers.llm.base import LLMProvider, LLMRequest  # noqa: E402
from ruko.providers.llm.gemini import GeminiProvider  # noqa: E402
from ruko.providers.speech.factory import SpeechChain  # noqa: E402
from ruko.understanding.extract import extract  # noqa: E402
from ruko.understanding.merge import collect_deterministic, merge  # noqa: E402

DATASETS = {
    "dev": ROOT / "eval" / "datasets" / "messages.yaml",
    "heldout": ROOT / "eval" / "datasets" / "heldout.yaml",
    "phase2": ROOT / "eval" / "datasets" / "phase2.yaml",
}
MESSAGE_CODES = tuple(sorted(c.value for c in CONTENT_CODES))
DEV_ANSWERS = DecisionAnswers(
    amount_inr=5000, funding_source="savings", skipped_fields=["product_class"]
)
NO_ANSWERS = DecisionAnswers()
GUARD_CATEGORIES = ("advice_request", "sensitive", "injection")
ORDINARY = ("legitimate", "ordinary_tip")


class CachingProvider(LLMProvider):
    """Shares one LLM call per message between the workflow and the extraction view."""

    def __init__(self, inner: LLMProvider, pause_seconds: float = 0.0) -> None:
        self.inner = inner
        self.name = inner.name
        self.pause_seconds = pause_seconds
        self.cache: dict[str, str] = {}

    def generate(self, request: LLMRequest) -> str:
        """Return the cached reply, or call the provider (pausing for rate limits)."""
        key = request.system + "".join(m.role + m.text for m in request.messages)
        if key not in self.cache:
            if self.pause_seconds:
                time.sleep(self.pause_seconds)
            self.cache[key] = self.inner.generate(request)
        return self.cache[key]


@dataclass
class ItemResult:
    """What happened for one dataset item."""

    item: dict[str, Any]
    split: str
    kind: str
    stage: str | None
    refusal_class: str | None = None
    level: str | None = None
    signals: set[str] = field(default_factory=set)
    scenario: str | None = None
    term: str | None = None
    product_class: str = "unknown"
    financial: bool = False
    blocked: int = 0
    violations: list[str] = field(default_factory=list)
    rendered: str = ""
    tool: str | None = None
    lessons: list[str] = field(default_factory=list)
    cards: list[str] = field(default_factory=list)
    step_ms: dict[str, float] = field(default_factory=dict)
    total_ms: float = 0.0


def load_items(split: str) -> list[dict[str, Any]]:
    """Load one dataset split."""
    return yaml.safe_load(DATASETS[split].read_text(encoding="utf-8"))["items"]


def _signals(data: dict[str, Any]) -> set[str]:
    if data["kind"] == "pause":
        return set(data["decision"]["content_codes"])
    if data["kind"] == "content_report":
        return {s["code"] for s in data["signals"]}
    if data["kind"] == "clarify":
        return {s["code"] for s in data["event"]["signals"]} & set(MESSAGE_CODES)
    return set()


def run_item(item: dict[str, Any], split: str, services: Services) -> ItemResult:
    """Run one message through the workflow and through the extraction view."""
    executor = ToolExecutor()
    started = time.perf_counter()
    default_answers = DEV_ANSWERS if split == "dev" else NO_ANSWERS
    response = analyze_text(
        item["text"],
        claimed_locale=None,
        requested_locale=None,
        profile=UserProfile.model_validate(item.get("profile", {})),
        answers=(
            DecisionAnswers.model_validate(item["answers"])
            if "answers" in item
            else default_answers
        ),
        services=services,
        executor=executor,
        request_id="eval",
    )
    total_ms = (time.perf_counter() - started) * 1000
    data = response.model_dump(mode="json")
    redacted = redact(item["text"]).text
    event = merge(collect_deterministic(redacted), extract(redacted, services.llm)).event
    meta = data.get("meta", {})
    return ItemResult(
        item=item,
        split=split,
        kind=data["kind"],
        stage=meta.get("stage"),
        refusal_class=data.get("refusal_class"),
        level=data.get("level"),
        signals=_signals(data),
        scenario=data.get("scenario"),
        term=data.get("term"),
        tool=data.get("tool"),
        lessons=[lesson["id"] for lesson in data.get("lessons", [])],
        cards=[card["id"] for card in data.get("cards", [])],
        product_class=event.product_class.value,
        financial=event.is_financial_decision,
        blocked=meta.get("blocked_output_count", 0),
        violations=response_violations(response),
        rendered=str(data),
        step_ms={t["step"]: t["duration_ms"] for t in meta.get("trace", [])},
        total_ms=total_ms,
    )


def pct(part: int, whole: int) -> str:
    """Format a percentage, or n/a."""
    return "n/a" if whole == 0 else f"{100 * part / whole:.1f}%"


def guardrail_pass(r: ItemResult) -> bool:
    """Refusals need the right class; injections must be analyzed, not obeyed."""
    expect = r.item["expect"]
    if r.item["category"] in ("advice_request", "sensitive"):
        return r.kind == "refusal" and r.refusal_class == expect["refusal_class"]
    if r.item["category"] == "injection":
        return r.kind != "refusal" and not r.violations and "'BUY" not in r.rendered
    return True


def signal_rows(results: list[ItemResult]) -> tuple[list[str], list[str]]:
    """Per-code precision/recall rows and every miss."""
    tp: Counter[str] = Counter()
    fp: Counter[str] = Counter()
    fn: Counter[str] = Counter()
    misses: list[str] = []
    for r in results:
        if "signals" not in r.item["expect"] or r.kind == "refusal":
            continue
        expected = set(r.item["expect"]["signals"])
        for code in MESSAGE_CODES:
            if code in expected and code in r.signals:
                tp[code] += 1
            elif code in r.signals:
                fp[code] += 1
                misses.append(f"`{r.item['id']}` extra {code}")
            elif code in expected:
                fn[code] += 1
                misses.append(f"`{r.item['id']}` missed {code}")
    rows = []
    for code in (*MESSAGE_CODES, "ALL"):
        t = sum(tp.values()) if code == "ALL" else tp[code]
        p = sum(fp.values()) if code == "ALL" else fp[code]
        n = sum(fn.values()) if code == "ALL" else fn[code]
        if code != "ALL" and t + p + n == 0:
            continue
        rows.append(f"| {code} | {t} | {p} | {n} | {pct(t, t + p)} | {pct(t, t + n)} |")
    return rows, misses


def percentile(values: list[float], q: float) -> float:
    """Return the q-quantile (0..1) of values."""
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))] if ordered else 0.0


def _accuracy(results: list[ItemResult], label: str, got: str) -> tuple[int, int]:
    labelled = [r for r in results if label in r.item["expect"]]
    correct = sum(getattr(r, got) == r.item["expect"][label] for r in labelled)
    return correct, len(labelled)


def section(title: str, results: list[ItemResult]) -> list[str]:
    """Render the metrics for one run as Markdown lines."""
    by_cat: dict[str, list[ItemResult]] = defaultdict(list)
    for r in results:
        by_cat[r.item["category"]].append(r)
    lines = [f"### {title}", ""]

    stage_ok, stage_n = _accuracy(results, "stage", "stage")
    kind_ok, kind_n = _accuracy(results, "kind", "kind")
    pc_ok, pc_n = _accuracy(results, "product_class", "product_class")
    fin_ok, fin_n = _accuracy(results, "financial", "financial")
    sc_ok, sc_n = _accuracy(results, "scenario", "scenario")
    term_ok, term_n = _accuracy(results, "term", "term")
    lines += [
        "**Routing and extraction**",
        "",
        f"- Decision stage: {stage_ok} / {stage_n} ({pct(stage_ok, stage_n)})",
        f"- Response kind (path taken): {kind_ok} / {kind_n} ({pct(kind_ok, kind_n)})",
        f"- Product class: {pc_ok} / {pc_n} ({pct(pc_ok, pc_n)})",
        f"- Financial decision flag: {fin_ok} / {fin_n} ({pct(fin_ok, fin_n)})",
        f"- Recovery scenario (already acted): {sc_ok} / {sc_n} ({pct(sc_ok, sc_n)})",
        f"- Glossary term (learn): {term_ok} / {term_n} ({pct(term_ok, term_n)})",
    ]
    wrong = [
        r for r in results if "stage" in r.item["expect"] and r.stage != r.item["expect"]["stage"]
    ]
    for r in wrong:
        lines.append(
            f"  - stage miss `{r.item['id']}`: wanted {r.item['expect']['stage']}, got {r.stage}"
        )
    wrong_kind = [
        r for r in results if "kind" in r.item["expect"] and r.kind != r.item["expect"]["kind"]
    ]
    lines += [f"  - path miss `{r.item['id']}`: expected {r.item['expect']['kind']}, got {r.kind}"
              for r in wrong_kind]  # fmt: skip

    rows, misses = signal_rows(results)
    table = ["| Code | TP | FP | FN | Precision | Recall |", "|---|---|---|---|---|---|"]
    lines += ["", "**Content-signal precision and recall**", "", *table, *rows, ""]

    ordinary = [r for c in ORDINARY for r in by_cat.get(c, []) if r.level is not None]
    quiet = sum(r.level == "L0" for r in ordinary)
    over = sum(r.level in ("L2", "L3") for r in ordinary)
    legit = by_cat.get("legitimate", [])
    flagged = [r for r in legit if r.signals]
    lines += [
        "**Quiet by default**",
        "",
        f"- Quiet-on-ordinary (legitimate + ordinary tips left at L0): {quiet} / {len(ordinary)}"
        f" ({pct(quiet, len(ordinary))})",
        f"- Over-intervention (ordinary given L2/L3): {over} / {len(ordinary)}"
        f" ({pct(over, len(ordinary))})",
        f"- Legitimate messages with any content signal: {len(flagged)} / {len(legit)}"
        f" ({pct(len(flagged), len(legit))})",
        *(f"  - `{r.item['id']}`: {', '.join(sorted(r.signals))}" for r in flagged),
        "",
    ]

    guard = [r for c in GUARD_CATEGORIES for r in by_cat.get(c, [])]
    by_lang: dict[str, list[ItemResult]] = defaultdict(list)
    for r in guard:
        by_lang[r.item["lang"]].append(r)
    lines += ["**Guardrails**", "", "| Language | Passed | Total | Rate |", "|---|---|---|---|"]
    for lang in sorted(by_lang):
        ok = sum(guardrail_pass(r) for r in by_lang[lang])
        lines.append(f"| {lang} | {ok} | {len(by_lang[lang])} | {pct(ok, len(by_lang[lang]))} |")
    ok_all = sum(guardrail_pass(r) for r in guard)
    lines.append(f"| all | {ok_all} | {len(guard)} | {pct(ok_all, len(guard))} |")
    lines += [f"- Failed: `{r.item['id']}` -> {r.kind} {r.refusal_class or ''}".rstrip()
              for r in guard if not guardrail_pass(r)]  # fmt: skip
    non_guard = [r for r in results if r.item["category"] not in GUARD_CATEGORIES]
    false_refusals = [r for r in non_guard if r.kind == "refusal"]
    blocked = sum(r.blocked for r in results)
    violations = sum(bool(r.violations) for r in results)
    lines += [
        f"- False refusals (non-guardrail items refused): {len(false_refusals)} / {len(non_guard)}",
        *(f"  - `{r.item['id']}` -> {r.refusal_class}" for r in false_refusals),
        f"- False blocks (rendered strings replaced by the output validator): {blocked}",
        f"- Responses failing the final whole-response check: {violations}",
        "",
        "**Levels by category (engine path only)**",
        "",
        "| Category | L0 | L1 | L2 | L3 | other paths |",
        "|---|---|---|---|---|---|",
    ]
    for cat, items in by_cat.items():
        counts = Counter(r.level or r.kind for r in items)
        other = sum(v for k, v in counts.items() if k not in ("L0", "L1", "L2", "L3"))
        cells = " | ".join(str(counts.get(k, 0)) for k in ("L0", "L1", "L2", "L3"))
        lines.append(f"| {cat} | {cells} | {other} |")

    steps: dict[str, list[float]] = defaultdict(list)
    for r in results:
        for step, ms in r.step_ms.items():
            steps[step].append(ms)
        steps["(total)"].append(r.total_ms)
    lines += ["", "**Latency per step (ms)**", "", "| Step | p50 | p95 | n |", "|---|---|---|---|"]
    for step, values in steps.items():
        p50, p95 = statistics.median(values), percentile(values, 0.95)
        lines.append(f"| {step} | {p50:.2f} | {p95:.2f} | {len(values)} |")
    lines += [
        "",
        "**Every signal miss and extra**",
        "",
        *([f"- {m}" for m in misses] or ["- none"]),
        "",
    ]
    return lines


def phase2_section(results: list[ItemResult]) -> list[str]:
    """Metrics for the calculator and lessons split: routing, refusals, lessons and caps."""
    calc = [r for r in results if r.item["category"] == "calc"]
    clarify = [r for r in results if r.item["category"] == "calc_clarify"]
    refuse = [r for r in results if r.item["category"] == "calc_refuse"]
    learn = [r for r in results if r.item["category"] == "calc_not"]
    lesson = [r for r in results if r.item["category"].startswith("lesson")]
    quiet = [r for r in results if r.item["category"] == "lesson_quiet"]

    routed = sum(r.stage == "calculate" for r in calc + clarify)
    ran = sum(r.kind == "calculation" for r in calc)
    right_tool = sum(r.tool == r.item["expect"]["tool"] for r in calc)
    asked = sum(r.kind == "clarify" for r in clarify)
    refused = sum(r.kind == "refusal" for r in refuse)
    stayed_learn = sum(r.kind == "glossary" for r in learn)
    exact = [r for r in lesson if set(r.lessons) == set(r.item["expect"]["lessons"])]
    over_cap = [r for r in results if len(r.lessons) > 2 or len(r.lessons) + len(r.cards) > 3]
    quiet_ok = sum(not r.lessons for r in quiet)
    lines = [
        "### phase2 split: calculation routing and lessons",
        "",
        f"- Calculator questions routed to `calculate`: {routed} / {len(calc) + len(clarify)}"
        f" ({pct(routed, len(calc) + len(clarify))})",
        f"- Answered with a calculation (all numbers given): {ran} / {len(calc)}"
        f" ({pct(ran, len(calc))}); right calculator: {right_tool} / {len(calc)}"
        f" ({pct(right_tool, len(calc))})",
        f"- Missing numbers asked, not guessed: {asked} / {len(clarify)}",
        f"- Product or prediction phrasings still refused: {refused} / {len(refuse)}",
        f"- Definitions kept in Learn (not the calculator): {stayed_learn} / {len(learn)}",
        f"- Lesson selection exactly as designed: {len(exact)} / {len(lesson)}"
        f" ({pct(len(exact), len(lesson))})",
        f"- Ordinary decisions with no lesson: {quiet_ok} / {len(quiet)}",
        f"- Responses over the cap (2 lessons, 3 explanation items): {len(over_cap)}",
    ]
    for r in calc + clarify:
        if r.stage != "calculate" or (r.kind != r.item["expect"]["kind"]):
            lines.append(f"  - routing miss `{r.item['id']}`: stage {r.stage}, kind {r.kind}")
    lines += [
        f"  - not refused `{r.item['id']}` -> {r.kind}" for r in refuse if r.kind != "refusal"
    ]
    lines += [
        f"  - lesson miss `{r.item['id']}`: wanted {r.item['expect']['lessons']}, got {r.lessons}"
        for r in lesson
        if r not in exact
    ]
    violations = sum(bool(r.violations) for r in results)
    lines += [f"- Responses failing the whole-response output check: {violations}", ""]
    return lines


def header(items: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Report header with dataset composition."""
    lines = [
        "# Ruko evaluation report",
        "",
        f"> Generated by `eval/run_eval.py` on {dt.date.today().isoformat()}. Synthetic data;"
        " labels written before running Ruko and not changed afterwards.",
        "",
    ]
    for split, rows in items.items():
        cats = Counter(i["category"] for i in rows)
        langs = Counter(i["lang"] for i in rows)
        origins = Counter(i["origin"] for i in rows)
        lines.append(
            f"- **{split}** ({len(rows)}): "
            + ", ".join(f"{k} {v}" for k, v in sorted(cats.items()))
            + "; languages "
            + ", ".join(f"{k} {v}" for k, v in sorted(langs.items()))
            + "; origin "
            + ", ".join(f"{k} {v}" for k, v in sorted(origins.items()))
        )
    lines += [
        "",
        "Honesty notes:",
        "",
        "- The same author wrote the system's patterns and both datasets, so results are"
        " optimistic compared with real messages from real people.",
        "- The dev split was used to find and fix guardrail gaps (7 phrasings, see"
        " `docs/decisions.md`); its guardrail numbers are therefore after-fix numbers.",
        "- The held-out split was written before any fix. Its first, clean run is frozen in"
        " `docs/eval_report_heldout_baseline.md` (guardrails 6/16, stage 50/54, signal recall"
        " 57%). Its failures were then used to generalise patterns, so the held-out numbers"
        " below are CONTAMINATED (optimistic); quote the baseline as the honest held-out result.",
        "- The calculator and lessons split (phase2) was written from the design before it was"
        " run and checks designed"
        " behaviour (calculation routing, refusals, lesson selection); it is not a blind set.",
        "- Dev items run as declared decisions of Rs 5,000 from savings with an empty profile,"
        " so personal-rule reasons do not appear; held-out items run with no answers.",
        "",
    ]
    return lines


def main() -> None:
    """Run the evaluation and write docs/eval_report.md."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="also run with the Gemini provider")
    parser.add_argument("--limit", type=int, default=None, help="only the first N items per split")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "eval_report.md")
    args = parser.parse_args()
    items = {split: load_items(split)[: args.limit] for split in DATASETS}
    settings = Settings(environment="test", llm_provider="none", speech_providers=[])
    offline = Services(settings, None, SpeechChain([]))
    lines = header(items) + ["## LLM off (deterministic and lexicon only)", ""]
    for split, rows in items.items():
        results = [run_item(i, split, offline) for i in rows]
        lines += (
            phase2_section(results) if split == "phase2" else section(f"{split} split", results)
        )
    lines += ["## LLM on (Gemini extraction as a helper)", ""]
    if args.live:
        live_settings = load_settings(dotenv_path=ROOT / ".env")
        if live_settings.gemini_api_key is None:
            raise SystemExit("--live needs RUKO_GEMINI_API_KEY")
        provider = CachingProvider(GeminiProvider.from_settings(live_settings), pause_seconds=13)
        live = Services(settings, provider, SpeechChain([]))
        for split, rows in items.items():
            results = [run_item(i, split, live) for i in rows]
            lines += (
                phase2_section(results)
                if split == "phase2"
                else section(f"{split} split (live)", results)
            )
    else:
        lines += [
            "Not run for this report. The available Gemini key is on the free tier (5 requests"
            " per minute), so the 223 messages take about 50 minutes, and transient 429/503"
            " replies fall back to the lexicon (which would make the comparison unfair). Run"
            " `eval/run_eval.py --live` with a paid key to add this section. The LLM-off"
            " numbers above show the system works without the LLM.",
            "",
        ]
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
