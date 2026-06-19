ALTER TABLE requirements_sets ADD COLUMN content_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE scenarios ADD COLUMN content_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE proposals ADD COLUMN content_hash TEXT NOT NULL DEFAULT '';

ALTER TABLE evaluations ADD COLUMN requirements_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE evaluations ADD COLUMN proposal_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE evaluations ADD COLUMN scenario_hash TEXT NOT NULL DEFAULT '';

ALTER TABLE requirements_sets
    ADD COLUMN role TEXT NOT NULL DEFAULT 'alternative'
    CHECK (role IN ('primary', 'alternative'));

UPDATE requirements_sets
SET role = 'primary'
WHERE id IN (
    SELECT rs.id
    FROM requirements_sets AS rs
    WHERE rs.id = (
        SELECT candidate.id
        FROM requirements_sets AS candidate
        WHERE candidate.project_id = rs.project_id
        ORDER BY candidate.created_at ASC, candidate.id ASC
        LIMIT 1
    )
);

CREATE UNIQUE INDEX idx_requirements_primary_per_project
    ON requirements_sets(project_id) WHERE role = 'primary';

ALTER TABLE vocabulary ADD COLUMN evaluator_recognized INTEGER NOT NULL DEFAULT 0;
