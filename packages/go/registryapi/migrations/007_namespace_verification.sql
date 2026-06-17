ALTER TABLE registry_namespaces
    DROP CONSTRAINT IF EXISTS registry_namespaces_status_check;

ALTER TABLE registry_namespaces
    ADD CONSTRAINT registry_namespaces_status_check
    CHECK (status IN ('pending_verification', 'active', 'reserved', 'suspended', 'rejected'));
