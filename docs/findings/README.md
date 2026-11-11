# Engineering findings

Short, sourced notes on things we learned the hard way while working on ANIP,
kept so the next person or agent does not have to rediscover them.

Each finding states:

- **Claim** — what to do or what is true.
- **Applies to** — everything, or one language, package or version.
- **Source** — the pull request, run or document that shows it.
- **Status** — `verified` (we did it and it worked), `observed once`, or
  `unverified` (believed, not checked).

Rules:

- A finding enters this folder through a reviewed pull request.
- Keep it to what was actually observed. Guesses are marked `unverified`.
- When a finding stops being true, correct it or delete it. Do not leave stale
  advice in place.
- Language-specific details are labelled. Do not assume a Python detail holds
  for Go, Java or C#.

Files:

- [porting-to-a-new-sdk-version.md](porting-to-a-new-sdk-version.md) — moving a
  binding to a new major version of a library it wraps.
- [local-verification.md](local-verification.md) — how to run each language's
  checks locally the way CI runs them.
