# Native API Backend Template

This template is local implementation material. Use it to call REST/OpenAPI-style or SDK-backed APIs after ANIP policy and approval checks have passed.

Implementation checklist:

- Resolve `connection_ref` to deploy-time configuration and secret refs.
- Build downstream requests only from `adapter_input` and reviewed backend input-contract fields.
- Reject unexpected backend options unless they are modeled as governed inputs such as `filters`, `fields`, or `adapter_options`.
- Normalize downstream errors into ANIP errors or preview results without leaking secrets.
- Record audit evidence for selected backend operation, outbound payload category, redaction, approval id, and downstream result id.
