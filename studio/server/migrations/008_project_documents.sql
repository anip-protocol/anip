CREATE TABLE project_documents (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'reference',
  filename TEXT NOT NULL,
  media_type TEXT NOT NULL DEFAULT 'application/octet-stream',
  source_path TEXT NOT NULL DEFAULT '',
  content BYTEA NOT NULL,
  content_hash TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX project_documents_project_idx
  ON project_documents(project_id, updated_at DESC);
