"""End-to-end smoke test: one command checks that the whole product works.

    .venv/Scripts/python scripts/smoke_test.py            # start the app locally and test it
    .venv/Scripts/python scripts/smoke_test.py --prod     # same, in the production configuration
    .venv/Scripts/python scripts/smoke_test.py --url https://your-service.run.app

It needs the built web app (``cd frontend && npm run build``). Locally it starts the real
backend, serving ``frontend/dist``, with the LLM off and fake speech (no keys, nothing
billed). With ``--url`` it tests an already running deployment instead (speech needs a real
provider there, so the speech check is then only run if it works).

Journeys: static layer and caching; share, pause, learn, decide, journal; a quiet L0 case;
calculation; recovery; refusal; the fictional broker's order-intent; language switch; and, when
Chrome or Edge is installed, a headless browser load of the built page to prove the bundle boots.
The ``--prod`` flag also checks that unverified lessons are hidden and verified facts shown.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
TIP = "Guaranteed 3x return in 7 days. Join our Telegram group, act today!"
BANDS = {"monthly_expenses_band": "25k_50k", "liquid_savings_band": "1l_3l"}
DEVANAGARI = re.compile(r"[\u0900-\u097F]")
KANNADA = re.compile(r"[\u0C80-\u0CFF]")
BROWSERS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "microsoft-edge",
)


class Report:
    """Collects PASS / FAIL / SKIP lines."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        """Record one check."""
        self.rows.append(("PASS" if ok else "FAIL", name, "" if ok else detail))
        return ok

    def skip(self, name: str, why: str) -> None:
        """Record a check that could not run."""
        self.rows.append(("SKIP", name, why))

    def show(self) -> int:
        """Print every row and return the number of failures."""
        for status, name, detail in self.rows:
            print(f"[{status}] {name}" + (f"  ->  {detail}" if detail else ""))
        failed = sum(status == "FAIL" for status, _, _ in self.rows)
        passed = sum(status == "PASS" for status, _, _ in self.rows)
        skipped = sum(status == "SKIP" for status, _, _ in self.rows)
        print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
        return failed


def free_port() -> int:
    """Ask the OS for an unused local port."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_server(prod: bool) -> tuple[subprocess.Popen[bytes], str]:
    """Start the real backend on a free port, serving the built web app."""
    dist = ROOT / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        raise SystemExit("Build the web app first: cd frontend && npm run build")
    port = free_port()
    env = {
        **os.environ,
        "RUKO_STATIC_DIR": str(dist),
        "RUKO_LLM_PROVIDER": "none",
        "RUKO_SPEECH_PROVIDERS": "fake",
        "RUKO_ENVIRONMENT": "prod" if prod else "dev",
        "RUKO_RATE_LIMIT_PER_MINUTE": "0",
        "RUKO_LOG_LEVEL": "WARNING",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ruko.main:app", "--port", str(port), "--no-access-log"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                return process, base
        except httpx.HTTPError:
            time.sleep(0.25)
    process.kill()
    raise SystemExit("The backend did not start in 20 seconds.")


def analyze(client: httpx.Client, text: str, **extra: object) -> dict:
    """POST /v1/analyze with a text input."""
    body = {"input": {"type": "text", "content": text}, "locale": "en", **extra}
    return client.post("/v1/analyze", json=body).json()


def static_checks(client: httpx.Client, r: Report) -> None:
    """The web app is served, cached correctly, and never shadows the API."""
    page = client.get("/")
    r.check("page: GET / serves the app", page.status_code == 200 and 'id="root"' in page.text)
    r.check("page: never cached", page.headers.get("cache-control") == "no-cache")
    r.check("page: sends a content security policy", "script-src 'self'" in page.headers.get(
        "content-security-policy", ""))  # fmt: skip
    asset = re.search(r'src="(/assets/[^"]+\.js)"', page.text)
    if r.check("page: references a built script", asset is not None, page.text[:200]):
        script = client.get(asset.group(1))
        r.check(
            "assets: served and immutable",
            script.status_code == 200 and "immutable" in script.headers.get("cache-control", ""),
        )
    worker = client.get("/sw.js")
    r.check("pwa: service worker served, not cached", worker.status_code == 200
            and worker.headers.get("cache-control") == "no-cache")  # fmt: skip
    manifest = client.get("/manifest.webmanifest").json()
    r.check("pwa: manifest has a GET share target for text", manifest["share_target"]["method"]
            == "GET" and "text" in manifest["share_target"]["params"])  # fmt: skip
    r.check("pwa: icons are served", all(
        client.get(icon["src"]).status_code == 200 for icon in manifest["icons"]))  # fmt: skip
    r.check("routing: /demo/broker gets the app", 'id="root"' in client.get("/demo/broker").text)
    unknown = client.get("/v1/not-a-route")
    r.check("routing: unknown API path is a JSON 404", unknown.status_code == 404
            and unknown.json().get("error", {}).get("code") == "NOT_FOUND")  # fmt: skip
    r.check("api: /health", client.get("/health").json().get("status") == "ok")
    r.check(
        "api: /docs lists the calculation kind", "calculation" in client.get("/openapi.json").text
    )


def journey_pause(client: httpx.Client, r: Report, prod: bool) -> None:
    """Share, clarify, pause, learn, speak, decide, journal."""
    first = analyze(client, TIP)
    r.check("share: a forwarded tip is asked three questions", first.get("kind") == "clarify"
            and len(first["questions"]) == 3, str(first)[:200])  # fmt: skip
    answers = {"amount_inr": 20000, "funding_source": "emergency_fund",
               "product_class": "scheme_or_app"}  # fmt: skip
    pause = analyze(client, TIP, answers=answers, profile=BANDS)
    is_pause = pause.get("kind") == "pause" and pause["level"] in ("L2", "L3")
    if not r.check(
        "pause: L2 or L3 for emergency money and a guaranteed-return claim",
        is_pause,
        str(pause)[:200],
    ):
        return
    r.check("pause: the user's own numbers are shown", bool(pause["numbers_text"]))
    r.check(
        "pause: every signal states its certainty",
        all(s["certainty_label"] for s in pause["signals"]),
    )
    r.check("pause: continuing is always available", pause["decision"]["override_allowed"] is True
            and bool(pause["override_label"]))  # fmt: skip
    lessons = pause.get("lessons", [])
    if prod:
        r.check("production: unverified lessons are hidden", lessons == [], str(lessons)[:200])
    else:
        r.check("learn: lessons chosen, at most 2, cards plus lessons at most 3",
                1 <= len(lessons) <= 2 and len(lessons) + len(pause["cards"]) <= 3)  # fmt: skip
        speech = client.post("/v1/speak", json={"locale": "en", "lesson_id": lessons[0]["id"]})
        r.check("listen: a lesson can be read aloud by ID", speech.status_code == 200
                and speech.json().get("kind") == "speech", speech.text[:200])  # fmt: skip
    event = pause["event"]
    codes = [reason["code"] for reason in pause["decision"]["reasons"]]
    entry = {
        "id": "smoke-1", "date": "2026-10-04", "stage": event["stage"],
        "product_class": event["product_class"], "source_type": event["source_type"],
        "level_shown": pause["level"], "reason_codes": codes,
        "action": "delayed", "overrode": False, "override_reason_given": False,
        "pause_completed": True, "could_state_why": True, "followed_own_rules": True,
    }  # fmt: skip
    review = client.post("/v1/journal/review", json={"locale": "en", "entries": [entry]}).json()
    r.check("journal: the device journal is reviewed, and nothing is kept", review.get("kind")
            == "journal_review" and review["total_decisions"] == 1, str(review)[:200])  # fmt: skip


def journey_rest(client: httpx.Client, r: Report, prod: bool) -> None:
    """Quiet case, calculation, recovery, refusal, broker, languages."""
    quiet = analyze(
        client, "Thinking of buying some Infosys shares",
        answers={"amount_inr": 2000, "funding_source": "savings", "product_class": "cash_equity"},
        profile={"experience": {"cash_equity": "some"}},
    )  # fmt: skip
    r.check(
        "quiet: an ordinary small decision stays at L0",
        quiet.get("level") == "L0",
        str(quiet)[:200],
    )
    calc = analyze(client, "What will my SIP of 5000 a month look like over 10 years?")
    r.check("calculate: scenarios side by side, labelled an illustration", calc.get("kind")
            == "calculation" and len(calc["scenarios"]) >= 2 and calc["is_illustration"] is True
            and bool(calc["assumptions"]), str(calc)[:200])  # fmt: skip
    r.check("calculate: no prediction wording", not re.search(
        r"you will (get|earn)|expected return", str(calc), re.I))  # fmt: skip
    acted = analyze(client, "I already paid 5000 by UPI and now they want a fee to withdraw")
    r.check("recovery: already acted goes to the recovery path", acted.get("kind") == "recovery")
    guide = client.post("/v1/recover", json={"locale": "en", "answers": {
        "paid_money": True, "payment_method": "upi", "cannot_withdraw": True}}).json()  # fmt: skip
    r.check("recovery: steps, a checklist and a draft you send yourself", guide.get("kind")
            == "recovery" and bool(guide["steps"]) and bool(guide["evidence_checklist"])
            and bool(guide["draft_complaint"]), str(guide)[:200])  # fmt: skip
    r.check(
        "recovery: no promise of a refund", not re.search(r"refund|money back", str(guide), re.I)
    )
    refusal = analyze(client, "Should I buy Reliance?")
    r.check("refusal: a stock question is refused", refusal.get("kind") == "refusal")
    glossary = analyze(client, "What is an IPO?")
    r.check(
        "learn: a definition gets the glossary, not a pause", glossary.get("kind") == "glossary"
    )
    report = analyze(client, "Is this message real? Guaranteed 3x return in 7 days")
    r.check("content: a report with signals and no verdict", report.get("kind") == "content_report"
            and bool(report["signals"]), str(report)[:200])  # fmt: skip
    broker = client.post("/v1/order-intent", json={
        "product_class": "derivative", "amount_band": {"min_inr": 30000, "max_inr": 50000},
        "borrowed_funds": True, "leveraged": True,
        "profile": {**BANDS, "rules": {"max_share_of_savings_pct": 10, "no_borrowed_money": True}},
    }).json()  # fmt: skip
    r.check("broker: the order-intent returns a level and reason codes only", broker.get("level")
            in ("L2", "L3") and bool(broker["reason_codes"]) and "text" not in broker
            and broker["override_allowed"] is True, str(broker)[:200])  # fmt: skip
    answers = {"amount_inr": 20000, "funding_source": "emergency_fund",
               "product_class": "scheme_or_app"}  # fmt: skip
    hindi = analyze(client, TIP, locale="hi", answers=answers, profile=BANDS)
    kannada = analyze(client, TIP, locale="kn", answers=answers, profile=BANDS)
    r.check(
        "language: Hindi pause is in Devanagari", bool(DEVANAGARI.search(hindi.get("headline", "")))
    )
    r.check(
        "language: Kannada pause is in Kannada script",
        bool(KANNADA.search(kannada.get("headline", ""))),
    )
    if prod:
        routes = client.post(
            "/v1/recover",
            json={"locale": "en", "answers": {"paid_money": True, "payment_method": "upi"}},
        ).text
        r.check("production: the verified helpline is shown", "1930" in routes)


def find_browser() -> str | None:
    """Return a Chrome or Edge executable, if one is installed."""
    for candidate in BROWSERS:
        found = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
        if found:
            return found
    return None


def browser_checks(base: str, r: Report) -> None:
    """Load the built pages in a headless browser and read the rendered page."""
    browser = find_browser()
    if browser is None:
        r.skip("browser: the built bundle boots", "no Chrome or Edge found")
        return
    for path, expected, name in (
        ("/", "Choose your language", "browser: first run shows the language choice"),
        (
            "/demo/broker",
            "Demo – not a real broker",
            "browser: the broker demo is plainly fictional",
        ),
    ):
        with tempfile.TemporaryDirectory() as profile:
            try:
                done = subprocess.run(
                    [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
                     f"--user-data-dir={profile}", "--virtual-time-budget=6000",
                     "--dump-dom", base + path],
                    capture_output=True, timeout=60, check=False,
                )  # fmt: skip
            except subprocess.TimeoutExpired:
                r.check(name, False, "the browser timed out")
                continue
        dom = done.stdout.decode("utf-8", errors="replace")
        r.check(name, expected in dom, f"rendered DOM did not contain {expected!r}")


def main() -> None:
    """Run the smoke test and exit non-zero if anything failed."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--url", help="test a running deployment instead of starting one")
    parser.add_argument("--prod", action="store_true", help="use (or expect) the production config")
    parser.add_argument("--no-browser", action="store_true", help="skip the headless browser step")
    args = parser.parse_args()

    process = None
    base = args.url.rstrip("/") if args.url else ""
    if not base:
        process, base = start_server(args.prod)
    report = Report()
    try:
        with httpx.Client(base_url=base, timeout=30) as client:
            static_checks(client, report)
            journey_pause(client, report, args.prod)
            journey_rest(client, report, args.prod)
        if not args.no_browser:
            browser_checks(base, report)
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=10)
    print(f"Smoke test against {base} ({'production' if args.prod else 'development'} config)\n")
    sys.exit(1 if report.show() else 0)


if __name__ == "__main__":
    main()
