"""Backend execution seam for generated capabilities."""
from __future__ import annotations

from typing import Any

BackendInvocationPlan = dict[str, Any]
GeneratedCapability = dict[str, Any]

class DefaultBackendAdapter:
    async def execute(self, capability: GeneratedCapability, plan: BackendInvocationPlan, _adapter_input: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
        if plan["unresolved_required_backend_inputs"]:
            return {
                "execution_status": "backend_input_incomplete",
                "capability_id": capability["capability_id"],
                "backend_input_contract": plan["backend_input_contract"],
                "unresolved_required_backend_inputs": plan["unresolved_required_backend_inputs"],
                "note": "Generated host is runnable, but backend-only inputs still require extension completion.",
            }
        if capability.get("execution_posture") == "approval_gated":
            return {
                "execution_status": "approval_required",
                "capability_id": capability["capability_id"],
                "title": capability["title"],
                "summary": capability["summary"],
                "semantic_input": plan["semantic_input"],
                "backend_input_contract": plan["backend_input_contract"],
                "approval_rule_refs": capability.get("governance", {}).get("approval_rule_refs", []),
                "note": "Generated host requires approval before backend execution.",
            }
        if capability.get("execution_posture") == "prepare_only":
            return {
                "execution_status": "prepared",
                "capability_id": capability["capability_id"],
                "semantic_input": plan["semantic_input"],
                "backend_input_contract": plan["backend_input_contract"],
                "note": "Generated host prepared a governed preview and did not execute the backend.",
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
