-- 007_service_metadata_artifacts.sql — Persist observed service metadata from Inspect

CREATE TABLE service_metadata_artifacts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('draft', 'active', 'archived')),
    data JSONB NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_service_metadata_project ON service_metadata_artifacts(project_id);
CREATE INDEX idx_service_metadata_updated ON service_metadata_artifacts(updated_at DESC);
