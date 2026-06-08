CREATE TABLE IF NOT EXISTS registry_templates (
    template_id TEXT NOT NULL,
    template_version TEXT NOT NULL,
    template_kind TEXT NOT NULL,
    project_type TEXT NOT NULL,
    anip_spec_version TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT '',
    industry TEXT NOT NULL DEFAULT '',
    systems JSONB NOT NULL DEFAULT '[]'::jsonb,
    publisher_id TEXT NOT NULL DEFAULT 'unknown',
    publisher_type TEXT NOT NULL DEFAULT 'unknown',
    manifest_digest TEXT NOT NULL,
    template_digest TEXT NOT NULL,
    package_digest TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    download_count BIGINT NOT NULL DEFAULT 0,
    manifest JSONB NOT NULL,
    template JSONB NOT NULL,
    package JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (template_id, template_version)
);

CREATE INDEX IF NOT EXISTS idx_registry_templates_listing
    ON registry_templates(download_count DESC, published_at DESC, template_id ASC, template_version DESC);

CREATE INDEX IF NOT EXISTS idx_registry_templates_filters
    ON registry_templates(template_kind, project_type, anip_spec_version, domain, industry);
