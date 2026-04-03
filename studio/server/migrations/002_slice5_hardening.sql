-- 002_slice5_hardening.sql — Slice 5: hashes, roles, evaluator_recognized

-- Per-artifact content hashes (recomputed on every create/update)
ALTER TABLE requirements_sets ADD COLUMN content_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE scenarios ADD COLUMN content_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE proposals ADD COLUMN content_hash TEXT NOT NULL DEFAULT '';

-- Per-artifact hashes on evaluations (frozen at evaluation save time)
ALTER TABLE evaluations ADD COLUMN requirements_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE evaluations ADD COLUMN proposal_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE evaluations ADD COLUMN scenario_hash TEXT NOT NULL DEFAULT '';

-- Requirements role: safe migration for existing data.
-- Step 1: Add nullable column first (no constraint yet)
ALTER TABLE requirements_sets ADD COLUMN role TEXT;

-- Step 2: Backfill — mark the oldest requirements set per project as primary, rest as alternative
UPDATE requirements_sets SET role = 'alternative';
UPDATE requirements_sets SET role = 'primary'
    WHERE id IN (
        SELECT DISTINCT ON (project_id) id
        FROM requirements_sets
        ORDER BY project_id, created_at ASC
    );

-- Step 3: Now enforce NOT NULL + CHECK
ALTER TABLE requirements_sets ALTER COLUMN role SET NOT NULL;
ALTER TABLE requirements_sets ALTER COLUMN role SET DEFAULT 'alternative';
ALTER TABLE requirements_sets ADD CONSTRAINT requirements_role_check
    CHECK (role IN ('primary', 'alternative'));

-- Step 4: Partial unique index — at most one primary per project
CREATE UNIQUE INDEX idx_requirements_primary_per_project
    ON requirements_sets(project_id) WHERE role = 'primary';

-- Vocabulary: evaluator_recognized flag
ALTER TABLE vocabulary ADD COLUMN evaluator_recognized BOOLEAN NOT NULL DEFAULT FALSE;
