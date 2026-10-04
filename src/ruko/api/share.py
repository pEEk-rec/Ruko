"""The share-sheet fallback: a share that reaches the server instead of the service worker.

Android posts shared text, links and photos to ``/share`` (the manifest's POST share target).
Normally the app's service worker answers that request on the phone. When it cannot (the
worker is not installed yet, or an older worker is still running), the request reaches the
server. Instead of dropping what was shared, the server hands it straight back inside the app
page as an inert JSON data block (never executed), and the app picks it up and starts the check.

Nothing here is stored or logged: the body is read in memory, echoed back once, and dropped.
The standard library's MIME parser reads the form, so no extra dependency is needed.
"""

from __future__ import annotations

import base64
import json
from email import policy
from email.parser import BytesParser
from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

MAX_SHARE_BYTES = 6_000_000
"""Largest share body read (a 4 MB screenshot plus multipart overhead)."""
MAX_IMAGE_BYTES = 4_000_000
IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})
TEXT_FIELDS = ("title", "text", "url")
DATA_BLOCK_ID = "ruko-shared"


def parse_share(content_type: str, body: bytes) -> dict[str, str] | None:
    """Read a multipart share form: ``{"image": base64}`` or the text fields, or None.

    An image of the wrong type or size gives ``{"unsupported": "1"}`` so the app can say so.
    """
    if not content_type.lower().startswith("multipart/form-data"):
        return None
    head = f"Content-Type: {content_type}\r\n\r\n".encode("latin-1", "replace")
    message = BytesParser(policy=policy.default).parsebytes(head + body)
    if not message.is_multipart():
        return None
    fields: dict[str, str] = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if name == "media":
            data = part.get_payload(decode=True) or b""
            if not data:
                continue
            if part.get_content_type() not in IMAGE_TYPES or len(data) > MAX_IMAGE_BYTES:
                return {"unsupported": "1"}
            return {"image": base64.b64encode(data).decode("ascii")}
        if name in TEXT_FIELDS:
            value = (part.get_payload(decode=True) or b"").decode("utf-8", "replace").strip()
            if value:
                fields[str(name)] = value
    return fields or None


def page_with_share(index_html: str, payload: dict[str, str]) -> str:
    """The app page with the shared content as an inert JSON data block before ``</body>``."""
    data = json.dumps(payload).replace("<", "\\u003c")
    block = f'<script type="application/json" id="{DATA_BLOCK_ID}">{data}</script>'
    if "</body>" in index_html:
        return index_html.replace("</body>", f"{block}</body>", 1)
    return index_html + block


async def _read_limited(request: Request) -> bytes | None:
    """The request body, or None if it is larger than ``MAX_SHARE_BYTES``."""
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_SHARE_BYTES:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def share_fallback_route(static_dir: Path, headers: dict[str, str]):  # noqa: ANN201
    """Build the ``POST /share`` handler for a frontend build in ``static_dir``."""

    async def share_fallback(request: Request) -> Response:
        """Hand a share that missed the service worker back to the app, or open the app."""
        body = await _read_limited(request)
        payload = (
            parse_share(request.headers.get("content-type", ""), body) if body is not None else None
        )
        if payload is None:
            return RedirectResponse("/", status_code=303)
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(
            page_with_share(index, payload),
            headers={**headers, "Cache-Control": "no-store"},
        )

    return share_fallback
