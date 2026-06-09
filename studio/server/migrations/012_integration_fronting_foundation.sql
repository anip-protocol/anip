-- 012_integration_fronting_foundation.sql
-- Deterministic foundation for governed integration-fronting projects.

ALTER TABLE projects
    ADD COLUMN project_type TEXT NOT NULL DEFAULT 'standard',
    ADD COLUMN integration_profile JSONB NOT NULL DEFAULT '{"kind":"none","systems":[]}';

CREATE INDEX idx_projects_project_type ON projects(project_type);

CREATE TABLE workspace_connections (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    backend_kind TEXT NOT NULL CHECK (backend_kind IN ('native_api', 'mcp', 'database', 'hybrid')),
    system_kind TEXT NOT NULL DEFAULT '',
    endpoint_ref TEXT NOT NULL DEFAULT '',
    auth_mode TEXT NOT NULL CHECK (auth_mode IN ('user_delegated', 'service_delegated', 'external')),
    identity_provider_ref TEXT NOT NULL DEFAULT '',
    secret_ref TEXT NOT NULL DEFAULT '',
    allowed_project_refs JSONB NOT NULL DEFAULT '[]',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_workspace_connections_workspace
    ON workspace_connections(workspace_id, updated_at DESC);

CREATE TABLE integration_discovery_records (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    connection_id TEXT REFERENCES workspace_connections(id) ON DELETE SET NULL,
    operation_id TEXT NOT NULL,
    backend_kind TEXT NOT NULL CHECK (backend_kind IN ('native_api', 'mcp', 'database', 'hybrid')),
    method TEXT NOT NULL DEFAULT '',
    path_template TEXT NOT NULL DEFAULT '',
    side_effect_level TEXT NOT NULL DEFAULT 'read',
    input_schema_summary JSONB NOT NULL DEFAULT '{}',
    risk_notes JSONB NOT NULL DEFAULT '[]',
    data JSONB NOT NULL DEFAULT '{}',
    content_hash TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_integration_discovery_records_project
    ON integration_discovery_records(project_id, updated_at DESC);

CREATE INDEX idx_integration_discovery_records_connection
    ON integration_discovery_records(connection_id);
