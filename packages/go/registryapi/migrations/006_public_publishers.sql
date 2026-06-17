CREATE TABLE IF NOT EXISTS registry_users (
    user_id UUID PRIMARY KEY,
    github_user_id TEXT UNIQUE,
    github_login TEXT,
    display_name TEXT NOT NULL,
    email TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_registry_users_github_login
    ON registry_users(lower(github_login))
    WHERE github_login IS NOT NULL AND github_login <> '';

CREATE TABLE IF NOT EXISTS registry_publishers (
    publisher_id TEXT PRIMARY KEY,
    publisher_type TEXT NOT NULL CHECK (publisher_type IN ('individual', 'organization', 'official')),
    display_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    website_url TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending_review', 'suspended')),
    trust_level TEXT NOT NULL DEFAULT 'unverified' CHECK (trust_level IN ('unverified', 'verified', 'official')),
    created_by_user_id UUID REFERENCES registry_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_registry_publishers_status
    ON registry_publishers(status, trust_level, publisher_id);

CREATE TABLE IF NOT EXISTS registry_publisher_memberships (
    publisher_id TEXT NOT NULL REFERENCES registry_publishers(publisher_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES registry_users(user_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'maintainer', 'publisher', 'viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (publisher_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_registry_publisher_memberships_user
    ON registry_publisher_memberships(user_id, role);

CREATE TABLE IF NOT EXISTS registry_namespaces (
    namespace TEXT PRIMARY KEY,
    publisher_id TEXT NOT NULL REFERENCES registry_publishers(publisher_id) ON DELETE RESTRICT,
    artifact_kinds JSONB NOT NULL DEFAULT '["package","template"]'::jsonb,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'reserved', 'suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_registry_namespaces_publisher
    ON registry_namespaces(publisher_id, status);

CREATE TABLE IF NOT EXISTS registry_publish_tokens (
    token_id UUID PRIMARY KEY,
    publisher_id TEXT NOT NULL REFERENCES registry_publishers(publisher_id) ON DELETE CASCADE,
    token_hash TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    scopes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by_user_id UUID REFERENCES registry_users(user_id) ON DELETE SET NULL,
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_registry_publish_tokens_publisher
    ON registry_publish_tokens(publisher_id, revoked_at, expires_at);

CREATE TABLE IF NOT EXISTS registry_artifact_ownership (
    artifact_kind TEXT NOT NULL CHECK (artifact_kind IN ('package', 'template')),
    artifact_id TEXT NOT NULL,
    publisher_id TEXT NOT NULL REFERENCES registry_publishers(publisher_id) ON DELETE RESTRICT,
    namespace TEXT NOT NULL REFERENCES registry_namespaces(namespace) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'transferred', 'suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (artifact_kind, artifact_id)
);

CREATE INDEX IF NOT EXISTS idx_registry_artifact_ownership_publisher
    ON registry_artifact_ownership(publisher_id, status, artifact_kind);

CREATE TABLE IF NOT EXISTS registry_audit_events (
    event_id UUID PRIMARY KEY,
    actor_user_id UUID REFERENCES registry_users(user_id) ON DELETE SET NULL,
    actor_publisher_id TEXT REFERENCES registry_publishers(publisher_id) ON DELETE SET NULL,
    token_id UUID REFERENCES registry_publish_tokens(token_id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_hash TEXT,
    user_agent_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_registry_audit_events_target
    ON registry_audit_events(target_type, target_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_registry_audit_events_actor
    ON registry_audit_events(actor_publisher_id, actor_user_id, created_at DESC);
