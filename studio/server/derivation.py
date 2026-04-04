"""Deterministic contract expectation derivation from shape + requirements."""

from __future__ import annotations

DECLARED_SURFACE_KEYS = [
    'budget_enforcement',
    'binding_requirements',
    'authority_posture',
    'recovery_class',
    'refresh_via',
    'verify_via',
    'followup_via',
    'cross_service_handoff',
    'cross_service_continuity',
    'cross_service_reconstruction',
]

_ALLOWED_RECOMMENDED_SHAPES = {
    'embedded_single_process',
    'production_single_service',
    'horizontally_scaled',
    'control_plane_worker_split',
    'multi_service_estate',
}


def derive_contract_expectations(
    shape_data: dict,
    requirements_data: dict,
) -> list[dict]:
    """Derive expected ANIP semantics from shape + requirements.
    Returns a list of expectation dicts: {surface, reason}
    """
    shape = shape_data.get('shape', shape_data)
    bc = requirements_data.get('business_constraints', {})
    audit = requirements_data.get('audit', {})
    permissions = requirements_data.get('permissions', {})
    expectations: list[dict] = []

    coordination = shape.get('coordination', [])
    if coordination:
        expectations.append({
            'surface': 'cross_service_handoff',
            'reason': 'shape has coordination edges between services',
        })
        expectations.append({
            'surface': 'cross_service_continuity',
            'reason': 'cross-service coordination requires continuity',
        })

    if any(e.get('relationship') == 'verification' for e in coordination):
        expectations.append({
            'surface': 'verify_via',
            'reason': 'shape has a verification coordination edge',
        })

    if any(e.get('relationship') == 'async_followup' for e in coordination):
        expectations.append({
            'surface': 'followup_via',
            'reason': 'shape has an async followup coordination edge',
        })

    all_capabilities: list[str] = []
    for svc in shape.get('services', []):
        all_capabilities.extend(svc.get('capabilities', []))

    cost_bearing_keywords = {'book', 'purchase', 'pay', 'deploy', 'provision', 'order'}
    has_cost_bearing = any(
        any(kw in cap.lower() for kw in cost_bearing_keywords)
        for cap in all_capabilities
    )

    if bc.get('spending_possible') and has_cost_bearing:
        expectations.append({
            'surface': 'budget_enforcement',
            'reason': 'requirements declare spending + shape has cost-bearing capabilities',
        })
    elif bc.get('cost_visibility_required') and has_cost_bearing:
        expectations.append({
            'surface': 'budget_enforcement',
            'reason': 'requirements declare cost visibility + shape has cost-bearing capabilities',
        })
    elif bc.get('spending_possible'):
        expectations.append({
            'surface': 'budget_enforcement',
            'reason': 'requirements declare spending (no cost-bearing capability found in shape -- consider adding one)',
        })

    if bc.get('approval_expected_for_high_risk') or permissions.get('preflight_discovery'):
        expectations.append({
            'surface': 'authority_posture',
            'reason': 'requirements declare approval expectations or preflight discovery',
        })

    if bc.get('recovery_sensitive') or bc.get('blocked_failure_posture'):
        posture = bc.get('blocked_failure_posture', '')
        if posture and posture != 'not_specified':
            expectations.append({
                'surface': 'recovery_class',
                'reason': f'requirements declare recovery sensitivity with {posture} posture',
            })
        else:
            expectations.append({
                'surface': 'recovery_class',
                'reason': 'requirements declare recovery sensitivity',
            })

    concepts = shape.get('domain_concepts', [])
    high_sensitivity = [c for c in concepts if c.get('sensitivity') == 'high']
    if high_sensitivity and not any(e['surface'] == 'authority_posture' for e in expectations):
        names = ', '.join(c['name'] for c in high_sensitivity)
        expectations.append({
            'surface': 'authority_posture',
            'reason': f'high-sensitivity concepts: {names}',
        })

    if audit.get('durable') and audit.get('cross_service_reconstruction_required'):
        expectations.append({
            'surface': 'cross_service_reconstruction',
            'reason': 'requirements declare durable audit with cross-service reconstruction',
        })

    return expectations


def _recommended_shape_for_validation(shape: dict, requirements_data: dict) -> str:
    shape_type = shape.get('type')
    if shape_type == 'multi_service':
        return 'multi_service_estate'

    preferred = requirements_data.get('scale', {}).get('shape_preference')
    if preferred in _ALLOWED_RECOMMENDED_SHAPES and preferred != 'multi_service_estate':
        return preferred

    return 'production_single_service'


def build_shape_backed_proposal(shape_data: dict, requirements_data: dict) -> dict:
    """Build a deterministic proposal-shaped evaluator input from a Shape.

    The current evaluator still consumes proposal-shaped data. For shape-first
    projects, derive the declared surfaces from the Shape + Requirements and
    synthesize the minimal proposal contract needed for evaluation.
    """
    shape = shape_data.get('shape', shape_data)
    expectations = derive_contract_expectations(shape_data, requirements_data)

    declared_surfaces = {key: False for key in DECLARED_SURFACE_KEYS}
    for expectation in expectations:
        surface = expectation.get('surface')
        if surface in declared_surfaces:
            declared_surfaces[surface] = True

    notes = [note.strip() for note in shape.get('notes', []) if isinstance(note, str) and note.strip()]
    service_names = [
        service.get('name') or service.get('id')
        for service in shape.get('services', [])
        if isinstance(service, dict) and (service.get('name') or service.get('id'))
    ]
    coordination_components = [
        f"coordination:{edge.get('relationship', 'handoff')}"
        for edge in shape.get('coordination', [])
        if isinstance(edge, dict)
    ]

    rationale = notes[:3] or [
        'service design is derived from the current shape, domain concepts, and coordination edges',
    ]

    required_components = [f'service:{name}' for name in service_names]
    required_components.extend(coordination_components)
    if not required_components:
        required_components = ['service:primary']

    return {
        'proposal': {
            'recommended_shape': _recommended_shape_for_validation(shape, requirements_data),
            'rationale': rationale,
            'required_components': required_components,
            'optional_components': [],
            'key_runtime_requirements': [],
            'anti_pattern_warnings': [],
            'expected_glue_reduction': {},
            'declared_surfaces': declared_surfaces,
        },
    }
