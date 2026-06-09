# GTM TypeScript Native Bundle

This bundle is the TypeScript-native GTM implementation for language parity.

It is different from `gtm_pipeline_typescript_proxy`: this bundle must not call the
Python ANIP services. It fills generated extension seams with TypeScript code that
owns GTM behavior behind the generated ANIP service boundary.

Implementation material in this bundle may call non-ANIP backends such as Postgres,
Cube, REST helper APIs, or MCP helper APIs, but it must not use the Python ANIP
services as its execution engine.

Required environment:

- `ANIP_API_KEYS_JSON`: inbound API key to principal map
- `DATABASE_URL`: GTM Postgres database URL, defaults to `postgresql://anip:anip@localhost:5454/anip_gtm`
- `GTM_PRIORITIZATION_BACKEND_URL`: optional REST helper backend, defaults to `http://127.0.0.1:9400`
- `GTM_PRIORITIZATION_BACKEND_TOKEN`: optional REST helper token
- `GTM_OUTREACH_BACKEND_URL`: optional MCP helper backend, defaults to `http://127.0.0.1:9500/mcp`
- `GTM_OUTREACH_BACKEND_TOKEN`: optional MCP helper token

