CREATE TABLE workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO workspaces (id, name, summary)
VALUES ('default', 'Default Workspace', 'Default Studio workspace')
ON CONFLICT (id) DO NOTHING;

ALTER TABLE projects ADD COLUMN workspace_id TEXT REFERENCES workspaces(id) ON DELETE CASCADE;

UPDATE projects
SET workspace_id = 'default'
WHERE workspace_id IS NULL;

CREATE INDEX idx_projects_workspace ON projects(workspace_id);
