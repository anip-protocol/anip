ALTER TABLE published_lineages
    ADD COLUMN IF NOT EXISTS publisher_id TEXT NOT NULL DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS publisher_type TEXT NOT NULL DEFAULT 'unknown';

ALTER TABLE registry_packages
    ADD COLUMN IF NOT EXISTS publisher_id TEXT NOT NULL DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS publisher_type TEXT NOT NULL DEFAULT 'unknown';

ALTER TABLE registry_receipts
    ADD COLUMN IF NOT EXISTS publisher_id TEXT NOT NULL DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS publisher_type TEXT NOT NULL DEFAULT 'unknown';
