# ANIP Tooling Can Start Before Later Phases

## Core Point

The scenario tooling does **not** depend on ANIP being "finished."

It depends on:

- a clear scenario format
- a clear evaluation rubric
- a clear understanding of what the current protocol can and cannot do

That means the tooling can start **now**, even while:

- Phase 2 Slice 1 is still being implemented
- Slice 2 is only a proposal
- Phase 3 and Phase 4 are still future roadmap work

## Why This Still Works

The tooling is not supposed to prove:

> ANIP solves everything already

It is supposed to answer:

> Given the protocol as it exists today, how much glue is still required for this scenario?

That is exactly why the result model matters:

- `HANDLED`
- `PARTIAL`
- `REQUIRES_GLUE`

The tool remains useful even when ANIP is incomplete, because incompleteness is part of what it reports.

## What Missing Future Phases Mean

Missing protocol work does not block the tooling.

It becomes part of the output.

Example:

- a scenario runs against current ANIP
- the result is `PARTIAL`
- the Glue Gap Analysis says:
  - authority clarification still missing
  - recovery branching still missing
  - cross-service coherence still incomplete

Later:

- Slice 2 lands
- Phase 3 lands
- Phase 4 lands

The same scenario can be re-run and may move:

- from `PARTIAL`
- toward `HANDLED`

That is not a problem.

That is the point.

## What Each Mode Can Do Now

### ANIP Validation Mode

This can be built immediately.

Input:

- one or more ANIP services
- one or more scenarios

Output:

- `HANDLED | PARTIAL | REQUIRES_GLUE`
- Glue Gap Analysis
- what the current ANIP surface already covers
- what still requires custom logic

This is the best first mode because it evaluates the current reality directly.

### Legacy Validation Mode

This can also be built before later ANIP phases.

Input:

- REST / GraphQL / MCP services
- the same scenarios

Output:

- Glue Gap Analysis
- missing control surfaces
- comparison against ANIP for the same scenario

This is likely the strongest public-facing mode because it answers:

> What is the current interface forcing the team to rebuild outside the interface?

### Design Mode

This can also start now, but it will improve over time.

Input:

- requirements
- scenarios

Output:

- proposed ANIP structure
- expected glue reduction
- likely weak spots

At first, Design Mode will propose around the current state of ANIP and explicitly call out what still remains unresolved.

As ANIP evolves, Design Mode becomes better.

## The Important Rule

The tooling should evaluate the **current** state of ANIP, not an imagined future state.

That means:

- current ANIP features are used as they actually exist
- missing phases are reported as remaining glue
- future protocol evolution improves results over time

This keeps the tooling honest and useful.

## Why This Is Actually Better

Starting the tooling early is not a compromise.

It is an advantage.

Because it lets ANIP evolve under pressure from real validation results:

- which scenarios are still only `PARTIAL`
- which glue categories remain
- which protocol additions actually move scenarios toward `HANDLED`

That creates the right feedback loop:

- implement protocol change
- run scenarios again
- observe whether glue was actually reduced

This is better than waiting until ANIP is "done," because ANIP should be shaped by the validator, not only by theory.

## Recommended Build Order

1. Build `ANIP Validation Mode` first
2. Build `Legacy Validation Mode` second
3. Let `Design Mode` improve over time as protocol maturity and scenario coverage increase

Why this order:

- validation works against current reality
- legacy comparison creates the clearest AHA moment
- design improves as the protocol and scenario corpus get stronger

## Practical Conclusion

Yes, the tooling can start now.

It does not need:

- Phase 2 Slice 2
- Phase 3
- Phase 4

to exist first.

Those later phases will improve the results, not unlock the existence of the tool.

That is the right framing:

> the tooling does not wait for ANIP to be complete; it helps show what ANIP can already handle and what still needs to evolve.
