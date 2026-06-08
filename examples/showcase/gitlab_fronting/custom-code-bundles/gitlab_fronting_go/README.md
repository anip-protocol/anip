# GitLab Fronting Go Bundle

Provider-specific backend adapter for generated Go GitLab fronting services.

The bundle overlays `extensions/backend_adapter.go` and adds a live Go test that
runs when `GITLAB_TOKEN` and `GITLAB_PROJECT_ID` are configured.
