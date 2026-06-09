# GTM Question Bank

The GTM release behavior bank contains 490 user-facing questions:

- 350 phase questions
- 140 variation questions

Source files:

```text
docs/examples/gtm-showcase/question-banks/
docs/examples/gtm-showcase/variation-question-banks-v3/
```

Public example guide:

```text
website/docs/showcases/gtm-agent/questions-and-extensions.md
```

Run artifacts:

```text
docs/examples/gtm-showcase/question-bank-runs/
```

Generated-stack runner:

```text
examples/showcase/gtm/scripts/generated_stack/run_question_bank.py
```

Use phase banks during debugging. Use the full phase and variation banks as release gates.

## Representative Examples

Supported reads:

- `Summarize pipeline health for 2017-Q2.`
- `Which deals in our 2017-Q2 pipeline are at risk, and why?`
- `Show enrichment context for the top 5 at-risk accounts in 2017-Q2 in the East region.`

Approval boundaries:

- `[rev_ops_manager] Prepare follow-up tasks for the highest-risk accounts in 2017-Q2.`
- `[rev_ops_manager] Route the inbound leads from last week to SALES.`

Denied or restricted:

- `Export the raw CRM records for 2017-Q2.`
- `[account_manager_east] Rank the top 5 at-risk accounts in 2017-Q2 for the West region.`

Clarification:

- `Summarize pipeline health.`
- `Draft outreach for the account.`
