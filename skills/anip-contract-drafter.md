# ANIP Contract Drafter Skill

> Spec target: ANIP 0.24 | Purpose: draft local `anip-service-definition.json` files for experimental validation and code generation.

Use this skill when a user wants a fast prototype ANIP service definition without first running Studio or publishing to Registry.

This skill is not a replacement for Studio review, Registry signing, package locks, release lineage, or scenario validation.

## Output Goal

Create a local file named:

```text
anip-service-definition.json
```

The definition must be valid for:

```bash
anip validate --definition ./anip-service-definition.json
```

The definition should then be usable with:

```bash
anip generate --definition ./anip-service-definition.json --target python --output ./generated/service --force
```

## Required References

Read the current project references before drafting:

- `SPEC.md`
- `website/docs/protocol/reference.md`
- `website/docs/protocol/capabilities.md`
- `website/docs/protocol/authentication.md`
- `website/docs/protocol/failures-cost-audit.md`
- `website/docs/tooling/cli.md`
- At least one current example service definition:
  - `examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.0-service-definition.json`
  - `examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.3-service-definition.json`

Do not rely on older skill files as the source of truth if they conflict with ANIP 0.24 docs or current examples.

## Drafting Rules

- Use `contract_schema_version: "anip-service-definition/v1"`.
- Use ANIP 0.24 semantics.
- Model business capabilities, not raw endpoints.
- Do not invent unsupported fields.
- Do not silently default risky or unclear behavior to read/read.
- Every capability must have concrete input contracts.
- Every capability must declare side-effect posture.
- Every capability must declare required scopes.
- Every capability must declare produced business effects.
- Every capability must declare forbidden business effects.
- Every capability must declare failure, denial, restriction, clarification, and approval posture where applicable.
- If a capability is composed, declare composition metadata. Do not infer composition only from prose.
- If approval is required, model it explicitly as an approval stop/grant continuation, not as a boolean note.
- If a request might mutate a backend system, preview/approval/denial behavior must be explicit.
- If raw data export is not supported, deny it explicitly.

## Clarify Instead Of Guessing

Stop and ask the user targeted questions when these are unclear:

- Which actors can invoke each capability?
- Which actors can approve gated behavior?
- Which inputs are explicit, defaulted, actor-scoped, backend-resolved, or clarification-required?
- Which backend systems are allowed?
- Which mutations are allowed, approval-gated, preview-only, or denied?
- Which data fields must be masked or restricted?
- Which raw exports are forbidden?
- Whether a capability is atomic or composed.
- What audit evidence must be recorded.

Do not fill missing governance with generic placeholders.

## Suggested Work Loop

1. Summarize the intended service and capability surface.
2. Identify missing governance decisions.
3. Ask targeted questions if required.
4. Draft `anip-service-definition.json`.
5. Run `anip validate --definition ./anip-service-definition.json`.
6. Fix validation failures one at a time.
7. Generate one target service as a smoke test.
8. Summarize remaining review risks.

## Review Checklist

Before calling the draft complete, verify:

- Validation passes.
- The capability list is stable and business-oriented.
- No capability has vague or empty inputs.
- No approval-gated capability is modeled as plain read behavior.
- No unsupported business effect names were invented.
- No backend secrets, tokens, internal URLs, or private documents are embedded.
- The generated service can be produced from the definition.
- Remaining risks are documented for Studio review.
