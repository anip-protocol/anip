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
