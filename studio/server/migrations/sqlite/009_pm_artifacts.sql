CREATE TABLE pm_artifacts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'frozen' CHECK (status IN ('draft', 'active', 'frozen', 'archived')),
    data TEXT NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_pm_artifacts_project ON pm_artifacts(project_id);
CREATE INDEX idx_pm_artifacts_updated ON pm_artifacts(updated_at DESC);
