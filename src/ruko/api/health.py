"""Health endpoint: status and version only."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ruko import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Liveness information. Deliberately contains nothing else."""

    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report that the service is up, and its version."""
    return HealthResponse(status="ok", version=__version__)
