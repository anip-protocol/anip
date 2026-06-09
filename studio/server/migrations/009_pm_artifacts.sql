-- 009_pm_artifacts.sql — Persist frozen PM-facing export artifacts

CREATE TABLE pm_artifacts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'frozen' CHECK (status IN ('draft', 'active', 'frozen', 'archived')),
    data JSONB NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_pm_artifacts_project ON pm_artifacts(project_id);
CREATE INDEX idx_pm_artifacts_updated ON pm_artifacts(updated_at DESC);
