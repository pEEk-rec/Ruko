"""Quotes: the user's own words behind a signal (E), and the rules that keep that safe."""

import pytest

from ruko.language.redact import redact
from ruko.models.common import Certainty, EvidenceSpan, ReasonCode, SignalSource
from ruko.models.event import Signal
from ruko.understanding.merge import collect_deterministic
from ruko.understanding.quotes import MAX_QUOTE, signal_quotes

TIP = (
    "Hello sir. Guaranteed 3x return in 7 days. Join our Telegram group, act today! "
    "Pay 5000 to rahul9876543210@ybl"
)


def signal(code: ReasonCode, text: str, needle: str) -> Signal:
    start = text.index(needle)
    return Signal(
        code=code,
        certainty=Certainty.LIKELY,
        source=SignalSource.LEXICON,
        evidence=EvidenceSpan(start=start, end=start + len(needle), text=needle),
    )


def test_a_quote_is_the_clause_around_the_match_not_just_the_keyword():
    quotes = signal_quotes([signal(ReasonCode.GUARANTEED_RETURN_CLAIM, TIP, "Guaranteed")], TIP)
    assert quotes[ReasonCode.GUARANTEED_RETURN_CLAIM] == "Guaranteed 3x return in 7 days."


def test_a_quote_is_always_a_plain_substring_of_the_message():
    text = "First line.\nSecond   line with   a    pitch: double your money fast!\nThird."
    quote = signal_quotes(
        [signal(ReasonCode.GUARANTEED_RETURN_CLAIM, text, "double your money")], text
    )
    value = quote[ReasonCode.GUARANTEED_RETURN_CLAIM]
    assert " ".join(value.split()) in " ".join(text.split())
    assert "Third" not in value and "First" not in value


def test_long_clauses_are_cut_at_a_word_with_an_ellipsis():
    text = "word " * 80 + "GUARANTEED " + "word " * 80
    quote = signal_quotes([signal(ReasonCode.GUARANTEED_RETURN_CLAIM, text, "GUARANTEED")], text)
    value = quote[ReasonCode.GUARANTEED_RETURN_CLAIM]
    assert len(value) <= MAX_QUOTE
    assert "GUARANTEED" in value


def test_only_the_first_signal_per_code_and_none_without_evidence():
    text = "Guaranteed returns. Guaranteed profit!"
    first = signal(ReasonCode.GUARANTEED_RETURN_CLAIM, text, "Guaranteed returns")
    second = signal(ReasonCode.GUARANTEED_RETURN_CLAIM, text, "Guaranteed profit")
    bare = Signal(
        code=ReasonCode.URGENCY_PRESSURE, certainty=Certainty.POSSIBLE, source=SignalSource.LEXICON
    )
    quotes = signal_quotes([first, second, bare], text)
    assert list(quotes) == [ReasonCode.GUARANTEED_RETURN_CLAIM]
    assert quotes[ReasonCode.GUARANTEED_RETURN_CLAIM].startswith("Guaranteed returns")


def test_a_span_outside_the_text_is_ignored_rather_than_crashing():
    bad = Signal(
        code=ReasonCode.URGENCY_PRESSURE,
        certainty=Certainty.POSSIBLE,
        source=SignalSource.LEXICON,
        evidence=EvidenceSpan(start=5, end=500, text="x"),
    )
    assert signal_quotes([bad], "short text") == {}


def test_control_characters_are_removed():
    text = "Act\x00 now\x07! Guaranteed\x1b return today."
    quote = signal_quotes([signal(ReasonCode.GUARANTEED_RETURN_CLAIM, text, "Guaranteed")], text)
    assert all(ord(ch) >= 32 for ch in quote[ReasonCode.GUARANTEED_RETURN_CLAIM])


def test_quotes_come_from_the_redacted_text_so_contact_details_are_placeholders():
    redacted = redact(TIP).text
    findings = collect_deterministic(redacted)
    quotes = signal_quotes(findings.signals, redacted)
    assert quotes, "the lexicon should find evidence in this message"
    joined = " ".join(quotes.values())
    assert "9876543210" not in joined and "rahul" not in joined


@pytest.mark.parametrize("hit", ["[UPI_USER]@ybl", "[PHONE]"])
def test_a_quote_that_is_only_a_placeholder_is_dropped(hit):
    text = f"Pay {hit}"
    sig = signal(ReasonCode.PAY_TO_INDIVIDUAL_ACCOUNT, text, hit)
    assert signal_quotes([sig], hit) == {}
