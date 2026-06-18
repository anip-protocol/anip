CREATE TABLE IF NOT EXISTS registry_browser_sessions (
    session_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES registry_users(user_id) ON DELETE CASCADE,
    session_hash TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_registry_browser_sessions_user
    ON registry_browser_sessions(user_id, revoked_at, expires_at);
