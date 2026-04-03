-- 001_initial.sql — ANIP Studio initial schema

-- Projects
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    domain TEXT NOT NULL DEFAULT '',
    labels JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_projects_domain ON projects(domain);
CREATE INDEX idx_projects_updated ON projects(updated_at DESC);

-- Requirements sets
CREATE TABLE requirements_sets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_requirements_project ON requirements_sets(project_id);

-- Scenarios
CREATE TABLE scenarios (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_scenarios_project ON scenarios(project_id);

-- Proposals
CREATE TABLE proposals (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requirements_id TEXT NOT NULL REFERENCES requirements_sets(id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_proposals_project ON proposals(project_id);
CREATE INDEX idx_proposals_requirements ON proposals(requirements_id);

-- Evaluations
CREATE TABLE evaluations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    proposal_id TEXT NOT NULL REFERENCES proposals(id),
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    requirements_id TEXT NOT NULL REFERENCES requirements_sets(id),
    result TEXT NOT NULL CHECK (result IN ('HANDLED', 'PARTIAL', 'REQUIRES_GLUE')),
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('live_validation', 'imported', 'manual')),
    data JSONB NOT NULL,
    input_snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_evaluations_project ON evaluations(project_id);
CREATE INDEX idx_evaluations_proposal ON evaluations(proposal_id);
CREATE INDEX idx_evaluations_scenario ON evaluations(scenario_id);

-- Vocabulary entries
CREATE TABLE vocabulary (
    id SERIAL PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    value TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT 'custom' CHECK (origin IN ('canonical', 'project', 'custom')),
    description TEXT NOT NULL DEFAULT '',
    UNIQUE(project_id, category, value)
);

-- Partial unique index for global vocabulary (project_id IS NULL).
-- Postgres UNIQUE constraints treat NULLs as distinct, so the table-level
-- UNIQUE(project_id, category, value) does not prevent duplicate global entries.
-- This index closes that gap.
CREATE UNIQUE INDEX idx_vocabulary_global_unique
    ON vocabulary(category, value) WHERE project_id IS NULL;

CREATE INDEX idx_vocabulary_category ON vocabulary(category);
CREATE INDEX idx_vocabulary_project ON vocabulary(project_id);
