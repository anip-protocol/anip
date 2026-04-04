"""Deterministic contract expectation derivation from shape + requirements."""


def derive_contract_expectations(
    shape_data: dict,
    requirements_data: dict,
) -> list[dict]:
    """Derive expected ANIP semantics from shape + requirements.
    Returns a list of expectation dicts: {surface, reason}
    """
    shape = shape_data.get("shape", shape_data)
    bc = requirements_data.get("business_constraints", {})
    audit = requirements_data.get("audit", {})
    permissions = requirements_data.get("permissions", {})
    expectations: list[dict] = []

    # Multi-service coordination implies cross-service surfaces
    coordination = shape.get("coordination", [])
    if coordination:
        expectations.append({
            "surface": "cross_service_handoff",
            "reason": "shape has coordination edges between services",
        })
        expectations.append({
            "surface": "cross_service_continuity",
            "reason": "cross-service coordination requires continuity",
        })

    # Verification coordination implies verify_via
    if any(e.get("relationship") == "verification" for e in coordination):
        expectations.append({
            "surface": "verify_via",
            "reason": "shape has a verification coordination edge",
        })

    # Async followup implies followup_via
    if any(e.get("relationship") == "async_followup" for e in coordination):
        expectations.append({
            "surface": "followup_via",
            "reason": "shape has an async followup coordination edge",
        })

    # Spending possible + shape has cost-bearing capabilities implies budget enforcement
    # This must inspect the shape, not just requirements -- the design says derivation
    # comes from shape + requirements together, not requirements alone.
    all_capabilities: list[str] = []
    for svc in shape.get("services", []):
        all_capabilities.extend(svc.get("capabilities", []))
    # NOTE: keyword matching is a first deterministic bridge. Later, capabilities
    # should gain an explicit cost_bearing: true classification on the shape service
    # so derivation is not name-sensitive. For now, this is acceptable.
    cost_bearing_keywords = {"book", "purchase", "pay", "deploy", "provision", "order"}
    has_cost_bearing = any(
        any(kw in cap.lower() for kw in cost_bearing_keywords)
        for cap in all_capabilities
    )

    if bc.get("spending_possible") and has_cost_bearing:
        expectations.append({
            "surface": "budget_enforcement",
            "reason": "requirements declare spending + shape has cost-bearing capabilities",
        })
    elif bc.get("cost_visibility_required") and has_cost_bearing:
        expectations.append({
            "surface": "budget_enforcement",
            "reason": "requirements declare cost visibility + shape has cost-bearing capabilities",
        })
    elif bc.get("spending_possible"):
        expectations.append({
            "surface": "budget_enforcement",
            "reason": "requirements declare spending (no cost-bearing capability found in shape -- consider adding one)",
        })

    # Approval expected implies authority posture
    if bc.get("approval_expected_for_high_risk") or permissions.get("preflight_discovery"):
        expectations.append({
            "surface": "authority_posture",
            "reason": "requirements declare approval expectations or preflight discovery",
        })

    # Recovery sensitive implies recovery class
    if bc.get("recovery_sensitive") or bc.get("blocked_failure_posture"):
        posture = bc.get("blocked_failure_posture", "")
        if posture and posture != "not_specified":
            expectations.append({
                "surface": "recovery_class",
                "reason": f"requirements declare recovery sensitivity with {posture} posture",
            })
        else:
            expectations.append({
                "surface": "recovery_class",
                "reason": "requirements declare recovery sensitivity",
            })

    # High-sensitivity concepts imply authority posture
    concepts = shape.get("domain_concepts", [])
    high_sensitivity = [c for c in concepts if c.get("sensitivity") == "high"]
    if high_sensitivity and not any(e["surface"] == "authority_posture" for e in expectations):
        names = ", ".join(c["name"] for c in high_sensitivity)
        expectations.append({
            "surface": "authority_posture",
            "reason": f"high-sensitivity concepts: {names}",
        })

    # Cross-service reconstruction
    if audit.get("durable") and audit.get("cross_service_reconstruction_required"):
        expectations.append({
            "surface": "cross_service_reconstruction",
            "reason": "requirements declare durable audit with cross-service reconstruction",
        })

    return expectations
