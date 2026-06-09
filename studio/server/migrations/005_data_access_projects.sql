-- 005_data_access_projects.sql — persisted governed data-access drafts

CREATE TABLE data_access_projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    state JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_data_access_projects_updated
    ON data_access_projects(updated_at DESC);
