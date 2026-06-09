ALTER TABLE registry_packages
    ADD COLUMN IF NOT EXISTS download_count BIGINT NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_registry_packages_downloads_published
    ON registry_packages(download_count DESC, published_at DESC, package_id ASC, package_version DESC);
