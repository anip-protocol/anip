# Studio-Generated GTM Pipeline Scaffold

This directory is generated from the seeded GTM Studio design.
It includes the generated ANIP service files plus the concrete GTM Phase 1 data module used by the showcase runtime.
Domain-specific refinements should live in explicit extension modules such as
`backend_extensions.py` and `service_extensions.py`, not as ad hoc edits inside
overwritten generated files.

Regenerate with:

```bash
PYTHONPATH=/Users/samirski/Development/ANIP python3 examples/showcase/gtm/scripts/generate_studio_scaffold.py
```
