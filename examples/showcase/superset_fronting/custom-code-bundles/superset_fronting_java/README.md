# Superset Fronting Java Custom Bundle

Adds a Superset REST backend adapter and live smoke test for the generated Java
Superset fronting service.

Required live-smoke environment:

- `SUPERSET_BASE_URL`
- `SUPERSET_USERNAME` and `SUPERSET_PASSWORD`, or `SUPERSET_ACCESS_TOKEN`
- `SUPERSET_WORKSPACE_SCOPE`
- `ANIP_SUPERSET_ALLOWED_WORKSPACES`

The live test calls the local Superset 6.1 REST API for bounded catalog
discovery and verifies chart/dataset write-adjacent capabilities only prepare
governed previews. It does not save charts, publish dashboards, execute raw SQL,
or mutate Superset state.
