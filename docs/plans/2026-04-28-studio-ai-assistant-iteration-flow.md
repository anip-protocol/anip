# Studio AI Assistant Iteration Flow

## Problem

The assistant flow must support iterative project design, not a one-shot button.
Most users will use the assistant heavily, so Studio must make the source context,
rerun behavior, and simulator feedback loop explicit.

Current pain points:

- PM drafting previously allowed only one source document.
- Uploading a new document did not create an obvious "rerun from updated context" flow.
- A completed action still looked like the same one-shot button.
- Developer drafting had similar rerun/restart ambiguity around the locked baseline.
- Simulator results were useful, but the path back into assistant-driven refinement was not obvious enough.

## Direction

Studio should treat assistant work as an iterative review loop:

1. Choose context: all sources by default, or an explicit selected subset.
2. Draft or rerun from the current context.
3. Review, answer clarifications, and save accepted sections.
4. Lock/advance deterministic artifacts.
5. Run readiness/simulation checks.
6. Feed simulator findings back into assistant-guided refinement.
7. Rerun, review, and publish only after the evidence is acceptable.

## Implemented First Slice

- PM assistant source context now supports `Use All Sources` and selective source checkboxes.
- Combined source previews include document title, kind, filename, and readable content.
- Source preview reloads when documents are added or updated.
- Draft bundles persist the full source document set, while keeping old single-document metadata for compatibility.
- Product drafting now clearly shows `Rerun AI Draft` and warns when selected sources changed after the draft.
- Developer drafting now clearly shows `Rerun AI Draft` and warns when the locked baseline changed after the draft.
- Developer assistant now exposes a direct handoff into the simulator/readiness loop.

## Next Slices

- Add draft history/revisions so users can compare assistant attempts instead of replacing the latest bundle in-place.
- Add a source-context snapshot panel showing exactly what will be sent before each run.
- Add a "Restart Flow" action that can optionally archive the current assistant bundle instead of deleting it.
- Let simulator failures open a targeted assistant refinement action for PM and Developer lanes.
- Add per-section rerun from changed context, not only rerun whole bundle or clarification-driven section redraft.
- Make accepted/obsolete assistant outputs clearer when source docs or locked baselines change.

## Non-Goals

- Do not make Studio nondeterministic. Assistant output remains proposed evidence until reviewed and saved.
- Do not hide app glue behind the assistant. The assistant may identify and draft glue guidance, but PM/dev must review it.
- Do not turn the simulator into a publication bypass. It is evidence and a gate, not a replacement for contract review.
