# Jira Fronting TypeScript Custom Bundle

This bundle fills the generated TypeScript backend adapter seam for the Jira fronting showcase.

It uses these runtime environment variables:

- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`

Live read capabilities call Jira REST. Write-adjacent capabilities return governed request previews and never mutate Jira.
