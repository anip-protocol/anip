# Dogfood Round 4: Checkpoints and Proofs Findings

Date: 2026-04-06

## Goal

Pressure ANIP's anchored-trust surfaces in one realistic Studio app by making the ANIP-only stress agent consume:

- checkpoint listing
- checkpoint detail
- inclusion proofs
- consistency proofs

instead of treating anchored trust as discovery-only metadata.

## What Was Exercised

- `GET /anip/checkpoints`
- `GET /anip/checkpoints/{checkpoint_id}?include_proof=true&leaf_index=0`
- `GET /anip/checkpoints/{checkpoint_id}?consistency_from=<prior-checkpoint>`
- posture-aware proof consumption in the Studio stress agent
- anchored trust on `studio-workbench` under `STUDIO_DOGFOOD_PROFILE=round4`

## Live Result

The final live ANIP-only Studio stress run succeeded against `http://127.0.0.1:8120`.

Checkpoint verification summary:

- mode: `strict`
- checkpoint count: `4`
- latest checkpoint: `ckpt-4`
- inclusion proof present: `true`
- inclusion proof path length: `5`
- consistency proof present: `true`
- consistency source: `ckpt-3`
- consistency proof path length: `6`
- latest last sequence: `28`
- latest entry count: `28`

Studio run outcomes remained strong while proofs were exercised:

- `Travel Booking Stress` -> `HANDLED`
- `Deployment Verify Stress` -> `HANDLED`
- `Order Follow-up Stress` -> `HANDLED`

## What Round 4 Proved

1. Anchored trust is now a real consumer surface in the Studio dogfood loop.
2. The ANIP client can consume checkpoint and proof endpoints over HTTP in a live run.
3. Studio can remain one realistic dogfood app while also pressuring ANIP proof surfaces.

## Real Issues Exposed During Dogfooding

Round 4 found several real runtime adoption bugs before it passed cleanly:

1. Studio advertised anchored trust, but mounted ANIP services were not being started explicitly inside the app lifespan.
   - Result: no live checkpoints were materializing.
   - Fix: explicitly start and stop the mounted ANIP services in `studio/server/app.py`.

2. Dogfood checkpoint scheduling was too slow for a live pressure run.
   - Result: the client raced checkpoint creation.
   - Fix: `round4` now uses a short checkpoint interval and the stress agent uses a short bounded retry when fetching checkpoints.

3. Checkpoint storage returned the oldest checkpoint slice instead of the most recent chronological slice.
   - Result: checkpoint numbering and checkpoint selection were wrong in live dogfooding.
   - Fix: storage now returns the most recent checkpoints in chronological order.

4. ANIP service startup was not idempotent.
   - Result: duplicate background schedulers could run against the same service and distort checkpoint behavior.
   - Fix: `ANIPService.start()`, `stop()`, and `shutdown()` are now idempotent.

5. Consistency proof payloads still contained raw bytes.
   - Result: `GET /anip/checkpoints/{id}?consistency_from=...` failed with HTTP `500` during the live run.
   - Fix: consistency proof paths are now serialized as hash strings.

## Conclusion

Round 4 is a success.

ANIP anchored trust is no longer just declarative metadata in the Studio dogfood harness. The client now consumes real checkpoints and real proof-bearing responses over the protocol, and the live Studio loop still completes successfully.

The strongest takeaway is not just that the proof surfaces exist. It is that dogfooding forced multiple real runtime corrections that made the proof surfaces actually consumable in practice.

## Next Pressure Area

Round 5 should target:

- observability hooks
- horizontal-scaling-style pressure

That is now the clearest under-exercised ANIP area after checkpoints and proofs.
