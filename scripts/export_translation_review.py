"""Export every Hindi and Kannada template as a review sheet for a native speaker.

All Hindi and Kannada text in Ruko is a machine-assisted draft (``status: draft``). A person who
reads the language should check it before anyone relies on it. This writes one CSV that opens
in any spreadsheet: the English line, the two drafts side by side, and empty columns for the
reviewer to mark each line OK or write a better one. Nothing here changes a template.

Run: ``python scripts/export_translation_review.py`` -> ``review_out/translation_review.csv``
(the folder is git-ignored: it is a generated working file, not part of the product).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ruko.language.templates import get_template_store  # noqa: E402

OUT = ROOT / "review_out" / "translation_review.csv"

# What a reader meets first: the Learn list and lessons, then the pause itself, then the rest.
GROUPS = [
    ("1 Learn: lessons", ("lesson.", "learn.topic.")),
    ("2 Learn: words", ("glossary.",)),
    ("3 Pause and reasons", ("pause.", "reason.", "certainty.", "signal.", "verdict.")),
    ("4 Questions", ("clarify.", "stage.", "question.", "reflect")),
    ("5 Calculators", ("calc.",)),
    ("6 Recovery", ("recovery.",)),
]


def group_of(key: str) -> str:
    """Name of the review group a template key belongs to."""
    for name, prefixes in GROUPS:
        if key.startswith(prefixes):
            return name
    return "7 Everything else"


def main() -> None:
    """Write the CSV and print how many lines there are per group."""
    store = get_template_store()
    keys = sorted(store.keys("en"), key=lambda k: (group_of(k), k))
    OUT.parent.mkdir(exist_ok=True)
    counts: dict[str, int] = {}
    with OUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["group", "key", "english", "hindi_draft", "kannada_draft",
             "hindi_ok (Y/N)", "hindi_better_wording", "kannada_ok (Y/N)", "kannada_better_wording"]
        )  # fmt: skip
        for key in keys:
            row = [store.get(loc, key) for loc in ("en", "hi", "kn")]
            group = group_of(key)
            counts[group] = counts.get(group, 0) + 1
            writer.writerow([group, key, *(t.text if t else "" for t in row), "", "", "", ""])
    for name in sorted(counts):
        print(f"{name}: {counts[name]}")
    print(f"written: {OUT} ({len(keys)} lines)")


if __name__ == "__main__":
    main()
