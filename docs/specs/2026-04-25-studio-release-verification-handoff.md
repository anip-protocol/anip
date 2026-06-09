# Studio Release Verification Handoff

## Context

Studio now has the core lineage model needed to distinguish draft work from delivery truth:

- Product and Developer revisions are immutable artifacts.
- PM Review can approve a specific Product revision, Developer revision, and compiled contract signature.
- Studio-local publications can be created before approval for local testing.
- Remote Registry publication and local-to-Registry promotion are blocked unless PM approval matches the current revision chain.
- Registry publish requires server-side authorization.
- Registry receipts are signed by the Registry and include publisher identity.
- Studio can run the verifier against local bundles and remote Registry packages.
- Release records can be created for approved remote Registry publications.

The remaining gap is that release state is not yet hard-gated on verified package provenance.

## Current Implementation State

Implemented commits:

- `f4831ab0 Require Registry publish authorization`
- `1dfa70de Add approval release lineage`

Current behavior:

- `DeveloperDefinitionView` computes PM approval lineage from the existing `design_traceability` artifact.
- Remote publish is blocked unless the PM approval is current.
- Local publication is still allowed without approval because it is useful for pre-approval testing.
- Promotion from local publication to remote Registry is blocked unless approval is current.
- `Record Release` creates an `anip_release_record` artifact for the latest remote Registry publication.
- `ProjectVerificationView` shows PM approval and release state beside publication lineage.
- `RevisionHistoryView` badges revisions as published, PM approved, and released.

## Manual Flow To Validate

Use an existing project or create a small test project with current Product and Developer revisions.

Expected path:

1. Ensure Product Design is locked into a Product revision.
2. Save Developer Definition so it has a Developer revision and contract signature.
3. Confirm `Publish To Registry` is blocked before PM approval.
4. Open PM Review and save status as `Approved`.
5. Return to Developer Definition.
6. Publish to remote Registry or promote a verified local publication.
7. Run Registry verifier from Verification.
8. Record Release.
9. Confirm Verification shows the same Product revision, Developer revision, package, receipt, PM approval, and release record.
10. Confirm Revision History shows both Product and Developer revisions as PM approved, published, and released.

Failure cases to check:

- Change Product Design after approval: remote publish should become blocked until a new approval targets the new revision chain.
- Save a new Developer revision after approval: remote publish should become blocked until PM approval targets the new Developer revision.
- Publish locally before approval: should still be allowed.
- Promote local to Registry before approval: should be blocked.
- Attempt to record release before remote publication: should be blocked.
- Attempt to record release twice for the same remote publication: should be blocked.

## Next Hardening Slice

Release should require both approved lineage and verified package provenance.

Target rule:

> A release record may only be created when the selected remote Registry publication targets the current approved revision chain and has passing verifier provenance.

Required behavior:

- Block `Record Release` if no Registry verifier evidence exists for the publication.
- Block `Record Release` if verifier status is failed, incomplete, unpublished, or mismatched.
- Require receipt status `verified`, not just `signed` or `present`.
- In production trust mode, require Registry trust policy checks to pass.
- Show a concrete release blocker message such as:
  - `Run Registry verifier before recording release.`
  - `Registry receipt is signed but not verified.`
  - `Registry trust policy failed for key <key_id>.`
  - `Verifier result targets a different package/version.`

## Likely Implementation Points

Primary files:

- `studio/src/views/DeveloperDefinitionView.vue`
- `studio/src/views/ProjectVerificationView.vue`
- `studio/src/views/RevisionHistoryView.vue`
- `studio/src/design/release-lineage.ts`
- `studio/src/design/external-cli-provenance.ts`
- `studio/src/design/publication-lineage.ts`

Useful existing data:

- Remote publication artifacts use `artifact_type: developer_registry_publication`.
- Verifier provenance artifacts use `artifact_type: external_cli_provenance_result`.
- verifier summaries already include package identity, receipt status, Registry signing mode, active key id, and trust posture.
- Release records use `artifact_type: anip_release_record`.

Recommended helper to add:

```ts
summarizeReleaseReadiness(pmArtifacts, currentRevisionContext): {
  status: 'ready' | 'blocked'
  label: string
  detail: string
  publicationArtifactId: string | null
  verifierArtifactId: string | null
}
```

That helper should reconcile:

- current approved Product/Developer revision chain
- latest remote Registry publication
- latest verifier provenance for that publication/package/version
- receipt status
- Registry trust policy status
- existing release records

## Done Criteria

This slice is done when:

- Release cannot be recorded until the matching remote Registry package has passing verifier provenance.
- Verification explains exactly why release is blocked or ready.
- Developer Definition uses the same readiness helper for the `Record Release` button.
- Revision History continues to show released badges only from actual release records.
- Tests cover ready, missing verifier, failed verifier, mismatched verifier, and already released cases.

Suggested tests:

- `release-lineage.test.ts`: add readiness cases.
- `publication-lineage.test.ts`: ensure publication matching stays stable.
- View-level smoke via existing Vitest build is sufficient unless a focused component test already exists.

