# Tooling Example Packs

These example packs serve two roles:

- stable baseline scenarios for ANIP slice validation
- pressure scenarios for newer protocol slices

Each pack is meant to be runnable through the validator using:

- `requirements.yaml`
- `proposal.yaml` (Approach artifact in current compatibility form)
- `scenario.yaml`

## Core Baseline

The current baseline packs are:

- `travel-single`
- `travel-multiservice`
- `devops-single`

These should be re-run for every major slice.

## Phase 3 Slice 2 Pressure Packs

The following packs exist specifically to pressure-test **advisory composition
hints** after `anip/0.16`:

- `travel-refresh-single`
  - stale quote requires a refresh path before booking
- `devops-wait-single`
  - temporary unavailability should expose a wait/retry path cleanly
- `manifest-revalidate-single`
  - manifest drift should expose a revalidation path before retry
- `devops-verify-single`
  - a side-effecting write should expose a likely verification capability
- `travel-followup-multiservice`
  - cross-service search / book / verify relationships should be discoverable

These are not workflow examples.

They are intended to answer:

> does the interface expose enough adjacent capability knowledge that teams stop
> encoding prerequisite, refresh, verification, and follow-up logic in wrappers
> and prompts?

## Phase 4 Slice 2 Pressure Packs

The following packs exist specifically to pressure-test **cross-service handoff
and adjacent-service relationship clarity** after `anip/0.18`:

- `travel-quote-handoff-multiservice`
  - one service produces a quote artifact and another must consume it
- `travel-refresh-handoff-multiservice`
  - a stale upstream artifact requires a discoverable cross-service refresh path
- `deploy-verify-multiservice`
  - one service performs the side effect and another is the natural verifier
- `trip-fanout-multiservice`
  - one planning step fans out into multiple downstream services
- `order-async-followup-multiservice`
  - a delayed downstream follow-up must remain reconstructable

These are meant to answer:

> after continuity is in place, does ANIP expose enough distributed handoff and
> relationship meaning that teams stop rebuilding adjacent-service logic in
> wrappers, orchestrators, and operator tooling?
