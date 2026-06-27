ALTER TABLE registry_packages
    ADD COLUMN IF NOT EXISTS lifecycle_status TEXT NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS lifecycle_reason TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS lifecycle_replacement_package_id TEXT,
    ADD COLUMN IF NOT EXISTS lifecycle_replacement_package_version TEXT,
    ADD COLUMN IF NOT EXISTS lifecycle_updated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS lifecycle_updated_by TEXT;

ALTER TABLE registry_packages
    DROP CONSTRAINT IF EXISTS registry_packages_lifecycle_status_check;

ALTER TABLE registry_packages
    ADD CONSTRAINT registry_packages_lifecycle_status_check
    CHECK (lifecycle_status IN ('active', 'superseded', 'deprecated', 'yanked', 'takedown'));

CREATE INDEX IF NOT EXISTS idx_registry_packages_lifecycle
    ON registry_packages(lifecycle_status, package_id, package_version);
