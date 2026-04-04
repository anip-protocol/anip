-- 004_workspaces.sql — top-level workspaces above projects

CREATE TABLE workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO workspaces (id, name, summary)
VALUES ('default', 'Default Workspace', 'Default Studio workspace')
ON CONFLICT (id) DO NOTHING;

ALTER TABLE projects ADD COLUMN workspace_id TEXT REFERENCES workspaces(id) ON DELETE CASCADE;

UPDATE projects
SET workspace_id = 'default'
WHERE workspace_id IS NULL;

ALTER TABLE projects ALTER COLUMN workspace_id SET NOT NULL;

CREATE INDEX idx_projects_workspace ON projects(workspace_id);
