# GTM Go Native Bundle

This bundle overlays the generated Go backend adapter and entrypoint so the Go
service owns GTM execution directly. It is native language parity evidence, not
a proxy to the Python showcase services.

Required environment:

- `DATABASE_URL`: Postgres connection for the GTM analytics schema.
- `ANIP_API_KEYS_JSON`: inbound API key to encoded actor-principal map.
- `ANIP_SERVICE_FILTER`: generated service id hosted by this process.
- `ANIP_SERVICE_ID`: service identity advertised by this process.

The bundle is implementation material. The signed ANIP contract still defines
the governed capability surface. The bundle must not mutate generated
declarations; it only fills the GTM-specific execution seams for Go.
