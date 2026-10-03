"""Link analysis on strings only. Ruko NEVER fetches, opens or follows a URL.

Features looked for: URL shorteners, messaging invite links, APK downloads, raw IP
hosts, plain ``http://``, punycode hosts, and lookalike domains that imitate a
regulator or market institution (brand name inside the domain, or one edit away).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

from ruko.data_files import load_yaml
from ruko.models.common import Certainty, ReasonCode, SignalSource
from ruko.models.event import Signal

_URL = re.compile(
    r"(?:https?://|www\.)[^\s<>\"'()]+"
    r"|\b(?:[a-z0-9-]+\.)+(?:com|in|net|org|io|app|xyz|top|live|site|online|info|co|me|ly|gl"
    r"|link|ws|cc|tk|gg|group|club|vip|biz|pro|cloud)\b(?:/[^\s<>\"'()]*)?",
    re.IGNORECASE,
)
_IP_HOST = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_HOMOGLYPHS = (("rn", "m"), ("vv", "w"), ("0", "o"), ("1", "l"), ("3", "e"), ("5", "s"))


@dataclass(frozen=True)
class LinkConfig:
    """Lists used by the analyzer, from data files."""

    shorteners: frozenset[str]
    invites: frozenset[str]
    affixes: frozenset[str]
    official: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class LinkFinding:
    """What the analyzer noticed about one link. Contains the host, never fetched content."""

    host: str
    features: tuple[str, ...]
    lookalike_of: str | None
    lookalike_strength: str | None


@lru_cache(maxsize=1)
def link_config() -> LinkConfig:
    """Load link lists and official domains (cached)."""
    raw = load_yaml("policy", "links.yaml")
    official = load_yaml("facts", "regulatory.yaml")["official_domains"]["value"]
    return LinkConfig(
        shorteners=frozenset(raw["shorteners"]),
        invites=frozenset(raw["messaging_invites"]),
        affixes=frozenset(raw["lookalike_affixes"]),
        official={brand: tuple(domains) for brand, domains in official.items()},
    )


def extract_links(text: str) -> list[str]:
    """Return link-like strings found in the text (no network access)."""
    return [m.group(0).rstrip(".,;:!?") for m in _URL.finditer(text)]


def _host(link: str) -> str:
    target = link if re.match(r"^https?://", link, re.IGNORECASE) else "http://" + link
    host = (urlsplit(target).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _is_official(host: str, config: LinkConfig) -> bool:
    return any(host == d or host.endswith("." + d) for ds in config.official.values() for d in ds)


def _edit_distance_one(a: str, b: str) -> bool:
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b, strict=True)) == 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return any(long_[:i] + long_[i + 1 :] == short for i in range(len(long_)))


def _unglyph(token: str) -> str:
    for fake, real in _HOMOGLYPHS:
        token = token.replace(fake, real)
    return token


def _lookalike(host: str, config: LinkConfig) -> tuple[str | None, str | None]:
    tokens = [t for t in re.split(r"[.\-]", host) if t]
    for brand in config.official:
        for raw_token in tokens:
            token = _unglyph(raw_token)
            if token == brand:
                return brand, "strong"
            if len(brand) >= 4 and brand in token:
                return brand, "strong"
            rest_after = token[len(brand) :] if token.startswith(brand) else None
            rest_before = token[: -len(brand)] if token.endswith(brand) else None
            if rest_after in config.affixes or rest_before in config.affixes:
                return brand, "strong"
            if len(brand) >= 4 and _edit_distance_one(token, brand):
                return brand, "weak"
    return None, None


def analyze_link(link: str) -> LinkFinding:
    """Analyze one link string.

    Args:
        link: A URL or bare domain.

    Returns:
        The features found. Official regulator domains get no features.
    """
    config = link_config()
    host = _host(link)
    if not host or _is_official(host, config):
        return LinkFinding(host=host, features=(), lookalike_of=None, lookalike_strength=None)
    path = urlsplit(link if "://" in link else "http://" + link).path.lower()
    features = []
    if host in config.shorteners:
        features.append("shortener")
    if host in config.invites or (host == "whatsapp.com" and path.startswith("/channel")):
        features.append("messaging_invite")
    if path.endswith(".apk") or "/apk" in path:
        features.append("apk")
    if _IP_HOST.match(host):
        features.append("ip_host")
    if link.lower().startswith("http://"):
        features.append("no_https")
    if host.startswith("xn--") or ".xn--" in host:
        features.append("punycode")
    brand, strength = _lookalike(host, config)
    if brand:
        features.append("lookalike")
    return LinkFinding(host, tuple(features), brand, strength)


def link_signals(text: str) -> tuple[list[Signal], list[LinkFinding]]:
    """Analyze every link in a text and turn features into signals.

    Args:
        text: Message text.

    Returns:
        Signals (with certainty) and the per-link findings.
    """
    findings = [analyze_link(link) for link in extract_links(text)]
    found: dict[ReasonCode, Certainty] = {}

    def add(code: ReasonCode, certainty: Certainty) -> None:
        if found.get(code) != Certainty.LIKELY:
            found[code] = certainty

    feature_count = sum(len(f.features) for f in findings)
    for finding in findings:
        features = set(finding.features)
        if finding.lookalike_of:
            strong = finding.lookalike_strength == "strong"
            add(
                ReasonCode.IMPERSONATION_SUSPECTED,
                Certainty.LIKELY if strong else Certainty.POSSIBLE,
            )
            add(ReasonCode.UNVERIFIED_PLATFORM_LINK, Certainty.LIKELY)
        if "apk" in features:
            add(ReasonCode.APP_INSTALL_REQUEST, Certainty.LIKELY)
            add(ReasonCode.UNVERIFIED_PLATFORM_LINK, Certainty.LIKELY)
        if "ip_host" in features or "punycode" in features:
            add(ReasonCode.UNVERIFIED_PLATFORM_LINK, Certainty.LIKELY)
        if features & {"shortener", "messaging_invite", "no_https"}:
            certainty = Certainty.LIKELY if feature_count >= 2 else Certainty.POSSIBLE
            add(ReasonCode.UNVERIFIED_PLATFORM_LINK, certainty)
        if "messaging_invite" in features:
            add(ReasonCode.UNSOLICITED_SOURCE, Certainty.POSSIBLE)
    signals = [Signal(code=c, certainty=v, source=SignalSource.RULE) for c, v in found.items()]
    return signals, findings
