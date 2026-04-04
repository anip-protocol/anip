"""Shape-internal reference validation."""


class ShapeIntegrityError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Shape integrity errors: {'; '.join(errors)}")


def validate_shape_integrity(shape_data: dict) -> None:
    """Validate all internal references within a shape artifact.
    Raises ShapeIntegrityError with a list of all violations.
    """
    shape = shape_data.get("shape", shape_data)
    errors: list[str] = []

    services = shape.get("services", [])
    service_ids = {s["id"] for s in services}
    concept_ids = {c["id"] for c in shape.get("domain_concepts", [])}

    # Enforce single_service / multi_service cardinality
    shape_type = shape.get("type")
    if shape_type == "single_service" and len(services) != 1:
        errors.append(f"single_service shape must have exactly 1 service, found {len(services)}")
    if shape_type == "multi_service" and len(services) < 2:
        errors.append(f"multi_service shape must have at least 2 services, found {len(services)}")

    # Check for duplicate IDs
    seen_services: set[str] = set()
    for s in shape.get("services", []):
        if s["id"] in seen_services:
            errors.append(f"duplicate service ID: {s['id']}")
        seen_services.add(s["id"])

    seen_concepts: set[str] = set()
    for c in shape.get("domain_concepts", []):
        if c["id"] in seen_concepts:
            errors.append(f"duplicate concept ID: {c['id']}")
        seen_concepts.add(c["id"])

    # Coordination edges must reference existing services
    for edge in shape.get("coordination", []):
        if edge["from"] not in service_ids:
            errors.append(f"coordination.from '{edge['from']}' is not a valid service ID")
        if edge["to"] not in service_ids:
            errors.append(f"coordination.to '{edge['to']}' is not a valid service ID")

    # Domain concept owners must reference services or "shared"
    for concept in shape.get("domain_concepts", []):
        owner = concept.get("owner")
        if owner and owner != "shared" and owner not in service_ids:
            errors.append(f"domain_concepts[{concept['id']}].owner '{owner}' is not a valid service ID")

    # owns_concepts must reference existing concept IDs
    for service in shape.get("services", []):
        for ref in service.get("owns_concepts", []):
            if ref not in concept_ids:
                errors.append(f"services[{service['id']}].owns_concepts '{ref}' is not a valid concept ID")

    if errors:
        raise ShapeIntegrityError(errors)
