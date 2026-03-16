"""Core types for the ANIP service runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from anip_core import CapabilityDeclaration, DelegationToken


@dataclass
class InvocationContext:
    """Context passed to capability handlers during invocation."""
    token: DelegationToken
    root_principal: str
    subject: str
    scopes: list[str]
    delegation_chain: list[str]
    invocation_id: str = ""
    client_reference_id: str | None = None
    _cost_actual: dict[str, Any] | None = field(default=None, repr=False)
    _progress_sink: Callable[[dict[str, Any]], Awaitable[None]] | None = field(default=None, repr=False)

    def set_cost_actual(self, cost: dict[str, Any]) -> None:
        """Set actual cost for variance tracking against declared cost."""
        self._cost_actual = cost

    async def emit_progress(self, payload: dict[str, Any]) -> None:
        """Emit a progress event. No-op if no sink is attached (unary mode)."""
        if self._progress_sink is not None:
            await self._progress_sink(payload)


# Handler type: (ctx, params) -> result dict (sync or async)
Handler = Callable[[InvocationContext, dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]


@dataclass
class Capability:
    """Bundles a capability declaration with its handler function."""
    declaration: CapabilityDeclaration
    handler: Handler
    exclusive_lock: bool = False


class ANIPError(Exception):
    """Structured error raised by capability handlers.

    Maps to an ANIP failure response with the given type and detail.
    """
    def __init__(self, error_type: str, detail: str) -> None:
        self.error_type = error_type
        self.detail = detail
        super().__init__(f"{error_type}: {detail}")
