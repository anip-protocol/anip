-- 006_application_integration_projects.sql — persisted application-integration drafts

CREATE TABLE application_integration_projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    state JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_application_integration_projects_updated
    ON application_integration_projects(updated_at DESC);
