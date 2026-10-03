"""The single, policy-checked tool executor.

Every workflow step runs through ``ToolExecutor.run``. It:

1. refuses any tool name not in ``data/policy/tools.yaml`` (``TOOL_NOT_ALLOWED``),
2. times the call and records a ``TraceStep`` (name, status, duration, reason codes;
   never content),
3. passes typed ``RukoError`` failures through and turns anything unexpected into
   ``TOOL_FAILED``, logging only the exception type.

The orchestrator chooses which tools to run; it never decides the intervention level.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal, TypeVar

from ruko.data_files import load_yaml
from ruko.errors import ErrorCode, RukoError
from ruko.models.common import ReasonCode
from ruko.models.responses import TraceStep
from ruko.observability import log_event

T = TypeVar("T")
StepStatus = Literal["ok", "skipped", "failed", "fallback"]


@lru_cache(maxsize=1)
def allowed_tools() -> frozenset[str]:
    """Return the tool allow-list (cached)."""
    return frozenset(load_yaml("policy", "tools.yaml")["allowed_tools"])


@dataclass
class ToolExecutor:
    """Runs allowed tools and keeps a content-free trace."""

    allowed: frozenset[str] = field(default_factory=allowed_tools)
    trace: list[TraceStep] = field(default_factory=list)

    def _check(self, name: str) -> None:
        if name not in self.allowed:
            log_event("tool_refused", logging.ERROR, tool=name)
            raise RukoError(ErrorCode.TOOL_NOT_ALLOWED)

    def run(self, name: str, tool: Callable[..., T], *args: object, **kwargs: object) -> T:
        """Run one tool call.

        Args:
            name: Tool name (must be in the allow-list).
            tool: The function to call.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            The tool's result.

        Raises:
            RukoError: ``TOOL_NOT_ALLOWED``, the tool's own typed error, or ``TOOL_FAILED``.
        """
        self._check(name)
        started = time.perf_counter()
        try:
            result = tool(*args, **kwargs)
        except RukoError:
            self._record(name, "failed", started)
            raise
        except Exception as error:  # noqa: BLE001 - converted to a typed error
            self._record(name, "failed", started)
            log_event("tool_failed", logging.ERROR, tool=name, exception_type=type(error).__name__)
            raise RukoError(ErrorCode.TOOL_FAILED) from None
        self._record(name, "ok", started)
        return result

    def note(self, name: str, status: StepStatus, reason_codes: Iterable[ReasonCode] = ()) -> None:
        """Change the status of the last step with this name, or record a skipped step."""
        self._check(name)
        for index in range(len(self.trace) - 1, -1, -1):
            if self.trace[index].step == name:
                self.trace[index] = self.trace[index].model_copy(
                    update={"status": status, "reason_codes": list(reason_codes)}
                )
                return
        self.trace.append(
            TraceStep(step=name, status=status, duration_ms=0.0, reason_codes=list(reason_codes))
        )

    def _record(self, name: str, status: StepStatus, started: float) -> None:
        duration = round((time.perf_counter() - started) * 1000, 2)
        self.trace.append(TraceStep(step=name, status=status, duration_ms=duration))
