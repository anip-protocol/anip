-- 010_link_saved_developer_drafts_to_projects.sql
-- Add an explicit Studio project link to persisted developer drafts.

ALTER TABLE data_access_projects
    ADD COLUMN studio_project_id TEXT REFERENCES projects(id) ON DELETE CASCADE;

CREATE INDEX idx_data_access_projects_studio_project
    ON data_access_projects(studio_project_id);

ALTER TABLE application_integration_projects
    ADD COLUMN studio_project_id TEXT REFERENCES projects(id) ON DELETE CASCADE;

CREATE INDEX idx_application_integration_projects_studio_project
    ON application_integration_projects(studio_project_id);
