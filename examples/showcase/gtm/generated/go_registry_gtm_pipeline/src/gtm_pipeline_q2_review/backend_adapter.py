"""Backend execution seam for generated capabilities."""
from __future__ import annotations

from typing import Any

type BackendInvocationPlan = dict[str, Any]
type GeneratedCapability = dict[str, Any]

class DefaultBackendAdapter:
    async def execute(self, capability: GeneratedCapability, plan: BackendInvocationPlan, _params: dict[str, Any]) -> dict[str, Any]:
        if plan["unresolved_required_backend_inputs"]:
            return {
                "execution_status": "backend_input_incomplete",
                "capability_id": capability["capability_id"],
                "backend_input_contract": plan["backend_input_contract"],
                "unresolved_required_backend_inputs": plan["unresolved_required_backend_inputs"],
                "note": "Generated host is runnable, but backend-only inputs still require extension completion.",
            }
        return {
            "execution_status": "backend_execution_stub",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "backend_input_contract": plan["backend_input_contract"],
            "note": "Replace DefaultBackendAdapter.execute() with provider-specific backend execution.",
        }

backend_adapter = DefaultBackendAdapter()
