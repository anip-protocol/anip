-- 003_shapes.sql — Shape artifact table + evaluation shape references

CREATE TABLE shapes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requirements_id TEXT NOT NULL REFERENCES requirements_sets(id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data JSONB NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_shapes_project ON shapes(project_id);
CREATE INDEX idx_shapes_requirements ON shapes(requirements_id);

-- Evaluation shape references (proposal_id becomes optional for backward compat)
ALTER TABLE evaluations ADD COLUMN shape_id TEXT REFERENCES shapes(id);
ALTER TABLE evaluations ADD COLUMN shape_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE evaluations ADD COLUMN derived_expectations JSONB;
ALTER TABLE evaluations ALTER COLUMN proposal_id DROP NOT NULL;
