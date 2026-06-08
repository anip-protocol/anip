# Phase 2 Question Bank

- Title: `Enrichment And Lookalike Questions`
- Questions: `50`

These questions are intended to show breadth of governed behavior, not a tiny canned prompt set.

## 1. enrichment-named-1

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Summarize firmographic context for Acme Corporation and Codehow.`

## 2. enrichment-named-2

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Summarize firmographic context for Condax and Acme Corporation.`

## 3. enrichment-named-3

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Summarize firmographic context for Codehow and Condax.`

## 4. enrichment-named-4

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Summarize firmographic context for Acme Corporation, Codehow, and Condax.`

## 5. cross-service-risk-enrichment-East

- Category: `cross_service`
- Expected outcome: `success`
- Question: `Show enrichment context for the top 5 at-risk accounts in 2017-Q2 in the East region.`

## 6. cross-service-risk-enrichment-West

- Category: `cross_service`
- Expected outcome: `success`
- Question: `Show enrichment context for the top 5 at-risk accounts in 2017-Q2 in the West region.`

## 7. cross-service-risk-enrichment-Central

- Category: `cross_service`
- Expected outcome: `success`
- Question: `Show enrichment context for the top 5 at-risk accounts in 2017-Q2 in the Central region.`

## 8. cross-service-risk-enrichment-company

- Category: `cross_service`
- Expected outcome: `success`
- Question: `Show enrichment context for the top 5 at-risk accounts in 2017-Q2 .`

## 9. lookalike-condax

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find lookalike accounts similar to Condax.`

## 10. lookalike-acme-corporation

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find lookalike accounts similar to Acme Corporation.`

## 11. lookalike-codehow

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find lookalike accounts similar to Codehow.`

## 12. lookalike-betasoloin

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find lookalike accounts similar to Betasoloin.`

## 13. lookalike-groovestreet

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find lookalike accounts similar to Groovestreet.`

## 14. clarify-enrichment-important-accounts

- Category: `clarification`
- Expected outcome: `clarification_required`
- Question: `Summarize firmographic context for our most important accounts.`

## 15. clarify-lookalike-best-customer

- Category: `clarification`
- Expected outcome: `clarification_required`
- Question: `Find lookalike accounts for our best customer.`

## 16. clarify-lookalike-top-account

- Category: `clarification`
- Expected outcome: `clarification_required`
- Question: `Find lookalike accounts for our top account.`

## 17. clarify-enrichment-core-accounts

- Category: `clarification`
- Expected outcome: `clarification_required`
- Question: `Summarize enrichment for our core accounts.`

## 18. clarify-buying-committee

- Category: `clarification`
- Expected outcome: `clarification_required`
- Question: `Show firmographic context for the companies we care about most.`

## 19. followup-lookalike-condax

- Category: `clarification_followup`
- Expected outcome: `success`
- Question: `Use Condax after asking for lookalike accounts for our best customer.`
- Notes: Follow-up turn after missing reference account.

## 20. followup-enrichment-acme-codehow

- Category: `clarification_followup`
- Expected outcome: `success`
- Question: `Use Acme Corporation and Codehow after asking for firmographic context for our most important accounts.`
- Notes: Follow-up turn after missing account scope.

## 21. followup-enrichment-acme-codehow-condax

- Category: `clarification_followup`
- Expected outcome: `success`
- Question: `Use Acme Corporation, Codehow, and Condax after asking for firmographic context for our most important accounts.`
- Notes: Follow-up turn after missing account scope.

## 22. deny-outreach-plus-rows

- Category: `denied`
- Expected outcome: `denied`
- Question: `Draft a personalized outreach sequence for the top 5 at-risk accounts in 2017-Q2 and include the raw underlying opportunity rows.`

## 23. deny-raw-enrichment-table

- Category: `denied`
- Expected outcome: `denied`
- Question: `Return the raw enrichment table for our highest-risk accounts.`

## 24. deny-buying-committee-export

- Category: `denied`
- Expected outcome: `denied`
- Question: `Export every enrichment field and underlying notes for Acme Corporation and Codehow.`

## 25. deny-enrichment-underlying-dump

- Category: `denied`
- Expected outcome: `denied`
- Question: `Dump the full underlying enrichment payload for Condax and Acme Corporation.`

## 26. deny-enrichment-debug-dump

- Category: `denied`
- Expected outcome: `denied`
- Question: `Return all raw enrichment records for internal debugging.`

## 27. deny-raw-lookalike-payload

- Category: `denied`
- Expected outcome: `denied`
- Question: `Give me the raw payload behind the Condax lookalike report.`

## 28. lookalike-top3-condax

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find the top 3 lookalike accounts similar to Condax.`

## 29. lookalike-top3-acme-corporation

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find the top 3 lookalike accounts similar to Acme Corporation.`

## 30. lookalike-top3-codehow

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find the top 3 lookalike accounts similar to Codehow.`

## 31. phase2-matrix-31

- Category: `cross_service`
- Expected outcome: `success`
- Question: `Summarize firmographic context for the top 3 at-risk accounts in 2017-Q2 for the East region.`

## 32. phase2-matrix-32

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find lookalike accounts similar to Acme Corporation in a bounded top-5 list.`

## 33. phase2-matrix-33

- Category: `clarification`
- Expected outcome: `clarification_required`
- Question: `Summarize firmographic context for the accounts we should review next.`

## 34. phase2-matrix-34

- Category: `cross_service`
- Expected outcome: `success`
- Question: `Summarize firmographic context for the top 3 at-risk accounts in 2017-Q2 for the East region.`

## 35. phase2-matrix-35

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find lookalike accounts similar to Groovestreet in a bounded top-5 list.`

## 36. phase2-matrix-36

- Category: `clarification`
- Expected outcome: `clarification_required`
- Question: `Summarize firmographic context for the accounts we should review next.`

## 37. phase2-matrix-37

- Category: `cross_service`
- Expected outcome: `success`
- Question: `Summarize firmographic context for the top 3 at-risk accounts in 2017-Q2 for the East region.`

## 38. phase2-matrix-38

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find lookalike accounts similar to Codehow in a bounded top-5 list.`

## 39. phase2-matrix-39

- Category: `clarification`
- Expected outcome: `clarification_required`
- Question: `Summarize firmographic context for the accounts we should review next.`

## 40. phase2-matrix-40

- Category: `cross_service`
- Expected outcome: `success`
- Question: `Summarize firmographic context for the top 3 at-risk accounts in 2017-Q2 for the East region.`

## 41. phase2-matrix-41

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find lookalike accounts similar to Condax in a bounded top-5 list.`

## 42. phase2-matrix-42

- Category: `clarification`
- Expected outcome: `clarification_required`
- Question: `Summarize firmographic context for the accounts we should review next.`

## 43. phase2-matrix-43

- Category: `cross_service`
- Expected outcome: `success`
- Question: `Summarize firmographic context for the top 3 at-risk accounts in 2017-Q2 for the East region.`

## 44. phase2-matrix-44

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find lookalike accounts similar to Betasoloin in a bounded top-5 list.`

## 45. phase2-matrix-45

- Category: `clarification`
- Expected outcome: `clarification_required`
- Question: `Summarize firmographic context for the accounts we should review next.`

## 46. phase2-matrix-46

- Category: `cross_service`
- Expected outcome: `success`
- Question: `Summarize firmographic context for the top 3 at-risk accounts in 2017-Q2 for the East region.`

## 47. phase2-matrix-47

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find lookalike accounts similar to Acme Corporation in a bounded top-5 list.`

## 48. phase2-matrix-48

- Category: `clarification`
- Expected outcome: `clarification_required`
- Question: `Summarize firmographic context for the accounts we should review next.`

## 49. phase2-matrix-49

- Category: `cross_service`
- Expected outcome: `success`
- Question: `Summarize firmographic context for the top 3 at-risk accounts in 2017-Q2 for the East region.`

## 50. phase2-matrix-50

- Category: `enrichment_happy_path`
- Expected outcome: `success`
- Question: `Find lookalike accounts similar to Groovestreet in a bounded top-5 list.`
