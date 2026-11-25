# Studio Showcase Snapshots

This directory contains frozen Studio project snapshots for published showcase
packages.

Use these snapshots for public Studio preload. Do not recreate published
showcases from hand-maintained seed data after a package is published, because
that can drift from the project/revision that produced the registry package.

To export a new snapshot from a running Studio database:

```bash
PYTHONPATH=. python studio/scripts/export-studio-project-snapshot.py \
  --project-id <studio-project-id> \
  --published-package <package-id>@<version> \
  --output studio/server/showcase_snapshots/<package-id>-<version>.studio-project-snapshot.json
```

Read-only/public showcase startup imports these snapshots after legacy seed
catalog data and replaces any existing project with the same snapshot project
ID.

Startup imports only the newest snapshot of each package (`latest_only`), so
older snapshots stay here as signed history and are not seeded or revalidated.
`gtm-pipeline-q2-review-0.4.6` was derived from the 0.4.5 snapshot rather than
exported: Developer Definition revision 2 carries the 0.4.6 permission intents
(no rule on a composed capability). Like the Slack and GitHub snapshots it has no
local publication: the package is the build-local bundle in
`examples/showcase/gtm/registry-packages`, whose development Registry receipt
Studio's local-publication verifier does not accept.
