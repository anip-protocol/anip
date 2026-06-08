CREATE TABLE IF NOT EXISTS published_lineages (
    id TEXT PRIMARY KEY,
    package_id TEXT NOT NULL,
    package_version TEXT NOT NULL,
    project_ref TEXT NOT NULL,
    product_revision_ref TEXT NOT NULL,
    developer_revision_ref TEXT NOT NULL,
    contract_signature TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'published' CHECK (status IN ('published', 'superseded', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_published_lineages_package_version
    ON published_lineages(package_id, package_version);

CREATE INDEX IF NOT EXISTS idx_published_lineages_project_ref
    ON published_lineages(project_ref);

CREATE INDEX IF NOT EXISTS idx_published_lineages_published_at
    ON published_lineages(published_at DESC);

CREATE TABLE IF NOT EXISTS registry_packages (
    package_id TEXT NOT NULL,
    package_version TEXT NOT NULL,
    published_lineage_id TEXT NOT NULL REFERENCES published_lineages(id) ON DELETE RESTRICT,
    project_ref TEXT NOT NULL,
    product_revision_ref TEXT NOT NULL,
    developer_revision_ref TEXT NOT NULL,
    contract_signature TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    manifest_digest TEXT NOT NULL,
    definition_digest TEXT NOT NULL,
    lock_digest TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    manifest JSONB NOT NULL,
    service_definition JSONB NOT NULL,
    recommended_lock JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (package_id, package_version)
);

CREATE INDEX IF NOT EXISTS idx_registry_packages_published_at
    ON registry_packages(published_at DESC);

CREATE TABLE IF NOT EXISTS registry_receipts (
    receipt_id TEXT PRIMARY KEY,
    package_id TEXT NOT NULL,
    package_version TEXT NOT NULL,
    registry_signature TEXT NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_registry_receipts_package
        FOREIGN KEY (package_id, package_version)
        REFERENCES registry_packages(package_id, package_version)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_registry_receipts_package
    ON registry_receipts(package_id, package_version);
