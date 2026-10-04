"""Serve the built frontend (``frontend/dist``) from the backend, so one container runs everything.

The app is a single-page app: any path that is not a file and not an API path (for example
``/demo/broker``) gets ``index.html``. API paths (``/v1``, ``/health``, ``/docs``,
``/openapi.json``) are registered first and are never answered by this mount, and an
unknown path under ``/v1`` is a JSON 404, never the HTML page.

Caching: hashed files under ``/assets/`` are immutable for a year; the page, the service worker
and the manifest are never cached, so a new release is picked up at once.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from ruko.api.share import share_fallback_route

NO_STORE_FILES = frozenset({"index.html", "sw.js", "manifest.webmanifest"})
API_PREFIXES = ("v1/", "health", "docs", "openapi.json", "redoc")
# The page loads only its own files. Inline styles are allowed (the app sets a few style values),
# data: images and audio are the user's own screenshot and Ruko's spoken answer.
PAGE_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; media-src 'self' data:; connect-src 'self'; object-src 'none'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def _is_api_path(path: str) -> bool:
    return path == "v1" or any(path.startswith(prefix) for prefix in API_PREFIXES)


class SPAStaticFiles(StaticFiles):
    """Static files with an ``index.html`` fallback for app routes and cache headers."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Return the file, or the app page for a route-like path that is not a file."""
        path = path.replace("\\", "/")  # Starlette joins with the OS separator
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            last = path.rsplit("/", 1)[-1]
            if exc.status_code != 404 or "." in last or _is_api_path(path):
                raise
            response = await super().get_response("index.html", scope)
            path = "index.html"
        name = path.rsplit("/", 1)[-1]
        if name in ("", "."):  # the root path is the app page
            name = "index.html"
        if path.startswith("assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif name in NO_STORE_FILES:
            response.headers["Cache-Control"] = "no-cache"
        if name == "index.html":
            response.headers["Content-Security-Policy"] = PAGE_CSP
        if name == "manifest.webmanifest":
            response.headers["Content-Type"] = "application/manifest+json"
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response


def mount_frontend(app: FastAPI, static_dir: Path | None) -> bool:
    """Mount the built frontend at ``/`` if ``static_dir`` holds a build.

    Must be called after every API router is included, so the API wins.

    Returns:
        True if the frontend was mounted.
    """
    if static_dir is None or not (static_dir / "index.html").is_file():
        return False
    page_headers = {"Content-Security-Policy": PAGE_CSP, **SECURITY_HEADERS}
    app.add_api_route(
        "/share",
        share_fallback_route(static_dir, page_headers),
        methods=["POST"],
        include_in_schema=False,
    )
    app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="frontend")
    return True
