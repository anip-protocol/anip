# Studio

This directory holds the GTM showcase Studio integration helpers.

Current contents:

- built-in seed project loaded through the Studio `/api/seed` endpoint
- `sync_observed_metadata.py`
  - fetches the live GTM pipeline service discovery + manifest documents
  - normalizes them into Studio's observed service metadata shape
  - upserts the seeded `gtm-pipeline-q2-review` project artifact

The goal is that a user opening Studio inside the showcase sees a complete,
preloaded GTM design and validation flow instead of an empty workspace, and
that the validation side reflects the running service rather than only static
seed data.
