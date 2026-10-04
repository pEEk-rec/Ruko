"""IPO and nomination glossary entries link to their SEBI investor-website topic pages."""

import pytest

from tests.helpers import analyze_body, make_client


@pytest.mark.parametrize(
    ("text", "url"),
    [
        ("What is an IPO?", "https://investor.sebi.gov.in/ipo_through_asba.html"),
        ("What is a nominee?", "https://investor.sebi.gov.in/market-nomination.html"),
        ("What is NAV?", "https://investor.sebi.gov.in"),
    ],
)
def test_glossary_entry_cites_its_sebi_page(text, url):
    data = make_client(llm=None).post("/v1/analyze", json=analyze_body(text)).json()
    assert data["kind"] == "glossary"
    assert [s["source_url"] for s in data["sources"]] == [url]
