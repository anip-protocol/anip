CREATE TABLE IF NOT EXISTS registry_abuse_reports (
    report_id UUID PRIMARY KEY,
    target_kind TEXT NOT NULL CHECK (target_kind IN ('package', 'template', 'publisher', 'namespace')),
    target_id TEXT NOT NULL,
    category TEXT NOT NULL,
    reason TEXT NOT NULL,
    reporter_contact TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'reviewing', 'resolved', 'rejected')),
    resolution TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_registry_abuse_reports_status
    ON registry_abuse_reports(status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_registry_abuse_reports_target
    ON registry_abuse_reports(target_kind, target_id, updated_at DESC);
