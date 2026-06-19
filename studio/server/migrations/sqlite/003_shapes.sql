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

CREATE INDEX idx_shapes_project ON shapes(project_id);
CREATE INDEX idx_shapes_requirements ON shapes(requirements_id);

ALTER TABLE evaluations ADD COLUMN shape_id TEXT REFERENCES shapes(id);
ALTER TABLE evaluations ADD COLUMN shape_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE evaluations ADD COLUMN derived_expectations TEXT;

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
