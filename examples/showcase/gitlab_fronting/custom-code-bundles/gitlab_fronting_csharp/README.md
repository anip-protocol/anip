# GitLab Fronting C# Bundle

Provider-specific backend adapter for generated C# GitLab fronting services.

The bundle overlays `BackendAdapter.cs` and adds a live xUnit smoke that runs
when `GITLAB_TOKEN` and `GITLAB_PROJECT_ID` are configured.
