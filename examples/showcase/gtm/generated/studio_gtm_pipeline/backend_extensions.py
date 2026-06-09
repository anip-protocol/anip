"""Non-generated backend extension hooks for the GTM pipeline service.

This file is intended to survive scaffold regeneration.
"""

from __future__ import annotations


def preprocess_backend_params(operation: str, params: dict) -> dict:
    normalized = dict(params or {})
    if operation == "fetch_product_pipeline_summary":
        owner_scope = str(normalized.get("owner_scope") or "").strip().lower()
        product_scope = str(normalized.get("product_scope") or "").strip()
        if product_scope and product_scope.lower() in {"east", "west", "central", "company", "all"}:
            if not owner_scope or product_scope.lower() == owner_scope:
                normalized["product_scope"] = None
    return normalized
