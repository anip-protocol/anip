# Engineering findings

Short, sourced notes on things we learned the hard way while working on ANIP,
kept so the next person or agent does not have to rediscover them.

Each finding keeps two things apart:

- **Observed** — what actually happened, with its **Source** (the pull request,
  run or document that shows it) and a **Status**:
  `verified` (we did it and saw it), `observed once` (seen in a single
  incident), or `unverified` (believed, not checked).
- **Recommendation** — the advice we draw from it. A recommendation is an
  opinion informed by the observation. It has not been shown to hold in general,
  however sensible it sounds.

Each finding also says what it **applies to**: everything, or one language,
package or version.

Rules:

- A finding enters this folder through a reviewed pull request.
- The status describes the observation only. Never mark a recommendation as verified.
- Keep observations to what actually happened. Guesses are marked `unverified`.
- When a finding stops being true, correct it or delete it. Do not leave stale
  advice in place.
- Language-specific details are labelled. Do not assume a Python detail holds
  for Go, Java or C#.

Files:

- [porting-to-a-new-sdk-version.md](porting-to-a-new-sdk-version.md) — moving a
  binding to a new major version of a library it wraps.
- [local-verification.md](local-verification.md) — how to run each language's
  checks locally the way CI runs them.
