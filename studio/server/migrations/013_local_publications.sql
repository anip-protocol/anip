-- 013_local_publications.sql — Immutable Studio-local registry records

CREATE TABLE local_publications (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    package_id TEXT NOT NULL,
    package_version TEXT NOT NULL,
    project_ref TEXT NOT NULL,
    product_revision_ref TEXT NOT NULL,
    developer_revision_ref TEXT NOT NULL,
    contract_signature TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    manifest_digest TEXT NOT NULL,
    definition_digest TEXT NOT NULL,
    package_record JSONB NOT NULL,
    receipt JSONB NOT NULL,
    authority TEXT NOT NULL DEFAULT 'local-studio',
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, package_id, package_version)
);

CREATE INDEX idx_local_publications_project ON local_publications(project_id, published_at DESC);
CREATE INDEX idx_local_publications_package ON local_publications(package_id, package_version);
