"""Stage 13: security and privacy review, as tests that keep holding after the review."""

import ast
import re
from pathlib import Path

import pytest

from ruko.config import Settings
from ruko.observability import ALLOWED_LOG_FIELDS
from tests.helpers import make_client

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "ruko"
NETWORK_MODULES = (
    "httpx", "requests", "urllib.request", "http.client", "socket", "aiohttp", "google"
)  # fmt: skip
# urllib.parse (pure string parsing, used by the link analyzer) is allowed everywhere.
NETWORK_ALLOWED = {
    SRC / "providers" / "http.py",
    SRC / "providers" / "llm" / "gemini.py",
    SRC / "providers" / "speech" / "sarvam.py",
}


def _python_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _imports(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_network_code_lives_only_in_the_three_provider_modules():
    offenders = []
    for path in _python_files():
        imports = _imports(ast.parse(path.read_text(encoding="utf-8")))
        uses_network = any(
            name == mod or name.startswith(mod + ".") for name in imports for mod in NETWORK_MODULES
        )
        if uses_network and path not in NETWORK_ALLOWED:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_no_url_from_user_content_is_ever_requested():
    # The provider modules call only fixed provider endpoints, never a URL from a message.
    for path in NETWORK_ALLOWED:
        source = path.read_text(encoding="utf-8")
        assert "extract_links" not in source and "analyze_link" not in source


def test_secrets_are_secretstr_and_come_only_from_the_environment():
    secret_fields = [n for n in Settings.model_fields if n.endswith("_api_key")]
    assert secret_fields
    for name in secret_fields:
        annotation = str(Settings.model_fields[name].annotation)
        assert "SecretStr" in annotation, name


KEY_LIKE = re.compile(r"AIza[0-9A-Za-z\-_]{30,}|sk-[A-Za-z0-9]{20,}|sk_[A-Za-z0-9]{20,}")


def test_no_key_like_strings_in_tracked_text_files():
    folders = ["src", "data", "docs", "tests", "eval", "spike"]
    files = [p for f in folders for p in (ROOT / f).rglob("*") if p.is_file()]
    files += [ROOT / "README.md", ROOT / ".env.example", ROOT / "Dockerfile"]
    hits = []
    for path in files:
        if path.suffix in {".png", ".pyc"} or "__pycache__" in path.parts:
            continue
        if KEY_LIKE.search(path.read_text(encoding="utf-8", errors="ignore")):
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []
    assert ".env" in (ROOT / ".gitignore").read_text(encoding="utf-8").split()


def _calls(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def test_every_log_call_uses_only_allow_listed_fields_and_a_constant_event():
    problems = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in _calls(tree):
            func = call.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name == "log_event":
                event = call.args[0] if call.args else None
                if not (isinstance(event, ast.Constant) and isinstance(event.value, str)):
                    problems.append(f"{path.name}: non-constant event name")
                extra = {k.arg for k in call.keywords if k.arg} - ALLOWED_LOG_FIELDS
                if extra:
                    problems.append(f"{path.name}: {sorted(extra)}")
            is_logger_method = name in {
                "debug",
                "info",
                "warning",
                "error",
                "exception",
                "critical",
            }
            if is_logger_method and path.name != "observability.py":
                problems.append(f"{path.name}: direct logger call")
            if name == "print":
                problems.append(f"{path.name}: print()")
    assert problems == []


SENTINEL = "QZXSECRETMESSAGE"


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/v1/analyze", {"input": {"type": "nonsense", "content": SENTINEL}}),
        ("/v1/analyze", {"input": {"type": "text", "content": SENTINEL}, "locale": "xx"}),
        ("/v1/speak", {"locale": "en", "items": [{"key": SENTINEL, "slots": {}}]}),
        ("/v1/recover", {"locale": "en", "answers": {"paid_money": SENTINEL}}),
        (
            "/v1/order-intent",
            {"product_class": SENTINEL, "amount_band": {"min_inr": 1, "max_inr": 2}},
        ),
    ],
)
def test_error_responses_never_echo_input(path, body):
    response = make_client().post(path, json=body)
    assert response.status_code >= 400
    assert SENTINEL not in response.text
    assert set(response.json()) == {"error"}


def test_production_defaults_hide_unverified_facts():
    assert Settings(environment="prod").unverified_facts_visible is False
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "RUKO_ENVIRONMENT=prod" in dockerfile


def test_production_api_hides_unverified_recovery_contacts():
    client = make_client(environment="prod")
    body = {"locale": "en", "answers": {"paid_money": True, "payment_method": "upi"}}
    data = client.post("/v1/recover", json=body).json()
    assert all(step["contact"] is None for step in data["steps"])
    assert data["meta"]["unverified_fact_ids"] == []


def test_data_sources_doc_lists_every_fact():
    from ruko.meta_info import fact_statuses

    doc = (ROOT / "docs" / "data_sources.md").read_text(encoding="utf-8")
    missing = [f.fact_id for f in fact_statuses() if f"`{f.fact_id}`" not in doc]
    assert missing == []
