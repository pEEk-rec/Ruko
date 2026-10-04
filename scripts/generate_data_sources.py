"""Regenerate docs/data_sources.md from data/facts/*.yaml (run from the repo root).

    .venv/Scripts/python scripts/generate_data_sources.py

The document lists every fact Ruko can display, its source, its verification status, the
owner's check notes and every open TODO_VERIFY item. It never changes a fact.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "data" / "facts"
OUT = ROOT / "docs" / "data_sources.md"


def _load(name: str) -> dict:
    return yaml.safe_load((FACTS / name).read_text(encoding="utf-8"))


def _one_line(text: object) -> str:
    return " ".join(str(text).split()).replace("|", "\\|") if text else ""


def _todo(entry: dict) -> str:
    if "todo_verify" in entry:
        return _one_line(entry["todo_verify"])
    for value in entry.values():
        if isinstance(value, str) and "TODO_VERIFY" in value:
            return _one_line(value)
    return ""


def _link(title: str, url: str | None) -> str:
    return f"[{_one_line(title)}]({url})" if url else _one_line(title)


def _yes_no(flag: object) -> str:
    return "yes" if flag else "no"


def main() -> None:
    """Write the document."""
    base = _load("base_rates.yaml")
    regulatory = _load("regulatory.yaml")
    routes = _load("recovery_routes.yaml")["routes"]
    todos: list[tuple[str, str]] = []
    lines = [
        "# Data sources",
        "",
        f"> Generated from `data/facts/*.yaml` on {dt.date.today().isoformat()} by",
        "> `scripts/generate_data_sources.py`. Every fact Ruko can display, its primary",
        "> source, the owner's check notes and its verification status. **Nothing is marked",
        "> verified by a human yet**: in production (`show_unverified_facts: false`) none of",
        "> these are shown until the owner sets `verified_by_human: true`.",
        "",
        "## Group statistics (`data/facts/base_rates.yaml`)",
        "",
        "| Fact ID | Value | Year | as_of | Source | Verified | Check note | TODO |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for fact in base["facts"]:
        source = base["sources"][fact["source"]]
        fact_id = f"base_rates:{fact['id']}"
        todo = _todo(fact)
        if todo:
            todos.append((fact_id, todo))
        lines.append(
            f"| `{fact_id}` | {fact['value']} | {fact['year']} | {fact['as_of']} | "
            f"{_link(source['source_title'], source['source_url'])} | "
            f"{_yes_no(fact['verified_by_human'])} | {_one_line(fact.get('checked_note'))} | "
            f"{'TODO_VERIFY' if todo else ''} |"
        )
    lines += [
        "",
        "Each statistic is shown only as a group statistic with SEBI's non-causal caveat (or",
        'Ruko\'s generic "group, not a prediction" caveat where the study has none).',
        "",
        "## Regulatory facts (`data/facts/regulatory.yaml`)",
        "",
        "| Fact ID | as_of | Source | Verified | Check note | TODO |",
        "|---|---|---|---|---|---|",
    ]
    for key, entry in regulatory.items():
        fact_id = f"regulatory:{key}"
        todo = _todo(entry)
        if todo:
            todos.append((fact_id, todo))
        lines.append(
            f"| `{fact_id}` | {entry['as_of']} | "
            f"{_link(entry['source_title'], entry.get('source_url'))} | "
            f"{_yes_no(entry['verified_by_human'])} | {_one_line(entry.get('checked_note'))} | "
            f"{'TODO_VERIFY' if todo else ''} |"
        )
    lines += [
        "",
        "## SEBI investor pages (`data/facts/investor_pages.yaml`)",
        "",
        "Linked from glossary entries (IPO, nomination).",
        "",
        "| Fact ID | as_of | Source | Verified | TODO |",
        "|---|---|---|---|---|",
    ]
    for key, entry in _load("investor_pages.yaml").items():
        fact_id = f"investor_pages:{key}"
        todo = _todo(entry)
        if todo:
            todos.append((fact_id, todo))
        lines.append(
            f"| `{fact_id}` | {entry['as_of']} | "
            f"{_link(entry['source_title'], entry.get('source_url'))} | "
            f"{_yes_no(entry['verified_by_human'])} | {'TODO_VERIFY' if todo else ''} |"
        )
    lines += [
        "",
        "## Recovery routes (`data/facts/recovery_routes.yaml`)",
        "",
        "| Fact ID | Contact | as_of | Source | Verified | Check note | TODO |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, entry in routes.items():
        fact_id = f"recovery_routes:{key}"
        todo = _todo(entry)
        if todo:
            todos.append((fact_id, todo))
        contact = entry.get("contact") or "(differs per bank / broker)"
        lines.append(
            f"| `{fact_id}` | {contact} | {entry['as_of']} | "
            f"{_link(entry['source_title'], entry.get('source_url'))} | "
            f"{_yes_no(entry['verified_by_human'])} | {_one_line(entry.get('checked_note'))} | "
            f"{'TODO_VERIFY' if todo else ''} |"
        )
    lines += ["", "## Open TODO_VERIFY items", ""]
    lines += [f"- `{fact_id}`: {text}" for fact_id, text in todos] or ["- none"]
    lines += [
        "",
        "## Not yet used",
        "",
        "- `data/facts/charges.yaml`: statutory trading charges for the cost calculator. Every",
        "  value is TODO_VERIFY and the file is disabled; the calculator uses only the user's own",
        "  or clearly hypothetical cost assumptions until the owner fills it from primary sources.",
        "",
        "## Other content that needs human review",
        "",
        "- Every Hindi and Kannada template (`data/templates/hi.yaml`, `kn.yaml`), lexicon",
        "  (`data/lexicon/`), stage pattern (`data/stages/`) and number-word file",
        "  (`data/language/`) is a draft for native-speaker review.",
        "- Glossary definitions (`glossary.*` templates) are Ruko's own wording, not SEBI quotes.",
        "  IPO and nomination link to SEBI topic pages; the other terms cite the investor website",
        "  home page (it has no stable per-term pages).",
        "- Policy numbers in `data/policy/intervention.yaml` and the example rates in",
        "  `data/policy/calculators.yaml` are proposals (see `docs/open_questions.md`).",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(todos)} TODO_VERIFY items)")


if __name__ == "__main__":
    main()
