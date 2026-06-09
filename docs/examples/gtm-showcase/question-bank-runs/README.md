# GTM Question-Bank Runs

This folder contains the executed broad-bank results for the GTM showcase.

The question banks prove breadth of coverage. The run artifacts prove that the
broader inventory was actually executed against the live stack.

Current broad-run status:

- Phase 1: `50 / 50`
- Phase 2: `50 / 50`
- Phase 3: `50 / 50`
- Phase 4: `50 / 50`
- Phase 5: `50 / 50`
- Phase 6: `50 / 50`
- Phase 7: `50 / 50`

Total:

- `350 / 350`

This broad-bank result was rerun after a small shared-runtime extraction:

- generic enum/default normalization moved into
  [packages/python/anip-runtime-utils](../../../packages/python/anip-runtime-utils)
- generic raw-export/direct-send preflight helpers moved into the same package

The result stayed green after that promotion pass.

Latest executed artifacts:

- [gtm_phase1_question_bank-latest.md](./gtm_phase1_question_bank-latest.md)
- [gtm_phase2_question_bank-latest.md](./gtm_phase2_question_bank-latest.md)
- [gtm_phase3_question_bank-latest.md](./gtm_phase3_question_bank-latest.md)
- [gtm_phase4_question_bank-latest.md](./gtm_phase4_question_bank-latest.md)
- [gtm_phase5_question_bank-latest.md](./gtm_phase5_question_bank-latest.md)
- [gtm_phase6_question_bank-latest.md](./gtm_phase6_question_bank-latest.md)
- [gtm_phase7_question_bank-latest.md](./gtm_phase7_question_bank-latest.md)

The broad-bank runner is:

- [run_question_bank.py](../../../../examples/showcase/gtm/scripts/run_question_bank.py)
