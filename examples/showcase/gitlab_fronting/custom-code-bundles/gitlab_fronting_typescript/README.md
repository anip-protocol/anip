# GitLab Fronting TypeScript Bundle

Provider-specific backend adapter for generated TypeScript GitLab fronting services.

The bundle overlays `src/runtime/backend-adapter.ts` and adds a live Vitest smoke
that runs when `GITLAB_TOKEN` and `GITLAB_PROJECT_ID` are configured.
