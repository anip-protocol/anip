ALTER TABLE registry_packages
    ADD COLUMN IF NOT EXISTS lock_digest TEXT NOT NULL DEFAULT 'sha256:missing-lock-digest';
