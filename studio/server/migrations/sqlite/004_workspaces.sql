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

PRAGMA legacy_alter_table = ON;
PRAGMA defer_foreign_keys = ON;

ALTER TABLE projects RENAME TO projects_old;

CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    domain TEXT NOT NULL DEFAULT '',
    labels TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE
);

INSERT INTO projects (
    id,
    name,
    summary,
    domain,
    labels,
    created_at,
    updated_at,
    workspace_id
)
SELECT
    id,
    name,
    summary,
    domain,
    labels,
    created_at,
    updated_at,
    workspace_id
FROM projects_old;

DROP TABLE projects_old;

CREATE INDEX idx_projects_domain ON projects(domain);
CREATE INDEX idx_projects_updated ON projects(updated_at DESC);
CREATE INDEX idx_projects_workspace ON projects(workspace_id);

ALTER TABLE requirements_sets RENAME TO requirements_sets_old;

CREATE TABLE requirements_sets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    content_hash TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'alternative' CHECK (role IN ('primary', 'alternative'))
);

INSERT INTO requirements_sets (
    id,
    project_id,
    title,
    status,
    data,
    created_at,
    updated_at,
    content_hash,
    role
)
SELECT
    id,
    project_id,
    title,
    status,
    data,
    created_at,
    updated_at,
    content_hash,
    role
FROM requirements_sets_old;

DROP TABLE requirements_sets_old;

CREATE INDEX idx_requirements_project ON requirements_sets(project_id);
CREATE UNIQUE INDEX idx_requirements_primary_per_project
    ON requirements_sets(project_id) WHERE role = 'primary';

ALTER TABLE scenarios RENAME TO scenarios_old;

CREATE TABLE scenarios (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    content_hash TEXT NOT NULL DEFAULT ''
);

INSERT INTO scenarios (
    id,
    project_id,
    title,
    status,
    data,
    created_at,
    updated_at,
    content_hash
)
SELECT
    id,
    project_id,
    title,
    status,
    data,
    created_at,
    updated_at,
    content_hash
FROM scenarios_old;

DROP TABLE scenarios_old;

CREATE INDEX idx_scenarios_project ON scenarios(project_id);

ALTER TABLE proposals RENAME TO proposals_old;

CREATE TABLE proposals (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requirements_id TEXT NOT NULL REFERENCES requirements_sets(id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    content_hash TEXT NOT NULL DEFAULT ''
);

INSERT INTO proposals (
    id,
    project_id,
    requirements_id,
    title,
    status,
    data,
    created_at,
    updated_at,
    content_hash
)
SELECT
    id,
    project_id,
    requirements_id,
    title,
    status,
    data,
    created_at,
    updated_at,
    content_hash
FROM proposals_old;

DROP TABLE proposals_old;

CREATE INDEX idx_proposals_project ON proposals(project_id);
CREATE INDEX idx_proposals_requirements ON proposals(requirements_id);

ALTER TABLE vocabulary RENAME TO vocabulary_old;

CREATE TABLE vocabulary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    value TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT 'custom' CHECK (origin IN ('canonical', 'project', 'custom')),
    description TEXT NOT NULL DEFAULT '',
    evaluator_recognized INTEGER NOT NULL DEFAULT 0,
    UNIQUE(project_id, category, value)
);

INSERT INTO vocabulary (
    id,
    project_id,
    category,
    value,
    origin,
    description,
    evaluator_recognized
)
SELECT
    id,
    project_id,
    category,
    value,
    origin,
    description,
    evaluator_recognized
FROM vocabulary_old;

DROP TABLE vocabulary_old;

CREATE UNIQUE INDEX idx_vocabulary_global_unique
    ON vocabulary(category, value) WHERE project_id IS NULL;
CREATE INDEX idx_vocabulary_category ON vocabulary(category);
CREATE INDEX idx_vocabulary_project ON vocabulary(project_id);

ALTER TABLE shapes RENAME TO shapes_old;

CREATE TABLE shapes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requirements_id TEXT NOT NULL REFERENCES requirements_sets(id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data TEXT NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO shapes (
    id,
    project_id,
    requirements_id,
    title,
    status,
    data,
    content_hash,
    created_at,
    updated_at
)
SELECT
    id,
    project_id,
    requirements_id,
    title,
    status,
    data,
    content_hash,
    created_at,
    updated_at
FROM shapes_old;

DROP TABLE shapes_old;

CREATE INDEX idx_shapes_project ON shapes(project_id);
CREATE INDEX idx_shapes_requirements ON shapes(requirements_id);

ALTER TABLE evaluations RENAME TO evaluations_old;

CREATE TABLE evaluations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    proposal_id TEXT REFERENCES proposals(id),
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    requirements_id TEXT NOT NULL REFERENCES requirements_sets(id),
    result TEXT NOT NULL CHECK (result IN ('HANDLED', 'PARTIAL', 'REQUIRES_GLUE')),
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('live_validation', 'imported', 'manual')),
    data TEXT NOT NULL,
    input_snapshot TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    requirements_hash TEXT NOT NULL DEFAULT '',
    proposal_hash TEXT NOT NULL DEFAULT '',
    scenario_hash TEXT NOT NULL DEFAULT '',
    shape_id TEXT REFERENCES shapes(id),
    shape_hash TEXT NOT NULL DEFAULT '',
    derived_expectations TEXT
);

INSERT INTO evaluations (
    id,
    project_id,
    proposal_id,
    scenario_id,
    requirements_id,
    result,
    source,
    data,
    input_snapshot,
    created_at,
    requirements_hash,
    proposal_hash,
    scenario_hash,
    shape_id,
    shape_hash,
    derived_expectations
)
SELECT
    id,
    project_id,
    proposal_id,
    scenario_id,
    requirements_id,
    result,
    source,
    data,
    input_snapshot,
    created_at,
    requirements_hash,
    proposal_hash,
    scenario_hash,
    shape_id,
    shape_hash,
    derived_expectations
FROM evaluations_old;

DROP TABLE evaluations_old;

CREATE INDEX idx_evaluations_project ON evaluations(project_id);
CREATE INDEX idx_evaluations_proposal ON evaluations(proposal_id);
CREATE INDEX idx_evaluations_scenario ON evaluations(scenario_id);

PRAGMA legacy_alter_table = OFF;
