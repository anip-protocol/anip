# Phase 3 Question Bank

- Title: `Actor-Aware Permission Questions`
- Questions: `50`

These questions are intended to show breadth of governed behavior, not a tiny canned prompt set.

## 1. actor-core-1

- Category: `actor-aware-core`
- Expected outcome: `success`
- Question: `[sales_leader] Rank the top 10 at-risk accounts in 2017-Q2.`
- Notes: Actor tag indicates the intended principal for the same governed question.

## 2. actor-core-2

- Category: `actor-aware-core`
- Expected outcome: `success`
- Question: `[sales_analyst] Rank the top 10 at-risk accounts in 2017-Q2.`
- Notes: Actor tag indicates the intended principal for the same governed question.

## 3. actor-core-3

- Category: `actor-aware-core`
- Expected outcome: `success`
- Question: `[account_manager_east] Rank the top 5 at-risk accounts in 2017-Q2.`
- Notes: Actor tag indicates the intended principal for the same governed question.

## 4. actor-core-4

- Category: `actor-aware-core`
- Expected outcome: `restricted`
- Question: `[account_manager_east] Rank the top 5 at-risk accounts in 2017-Q2 for the West region.`
- Notes: Actor tag indicates the intended principal for the same governed question.

## 5. actor-core-5

- Category: `actor-aware-core`
- Expected outcome: `denied`
- Question: `[sales_analyst] Prepare follow-up tasks for the highest-risk accounts in 2017-Q2.`
- Notes: Actor tag indicates the intended principal for the same governed question.

## 6. actor-core-6

- Category: `actor-aware-core`
- Expected outcome: `approval_required`
- Question: `[rev_ops_manager] Prepare follow-up tasks for the highest-risk accounts in 2017-Q2.`
- Notes: Actor tag indicates the intended principal for the same governed question.

## 7. actor-core-7

- Category: `actor-aware-core`
- Expected outcome: `success`
- Question: `[sales_analyst] Summarize firmographic context for Acme Corporation and Codehow.`
- Notes: Actor tag indicates the intended principal for the same governed question.

## 8. actor-core-8

- Category: `actor-aware-core`
- Expected outcome: `denied`
- Question: `[sales_analyst] Find lookalike accounts similar to Condax.`
- Notes: Actor tag indicates the intended principal for the same governed question.

## 9. actor-core-9

- Category: `actor-aware-core`
- Expected outcome: `success`
- Question: `[sales_leader] Find lookalike accounts similar to Condax.`
- Notes: Actor tag indicates the intended principal for the same governed question.

## 10. actor-core-10

- Category: `actor-aware-core`
- Expected outcome: `success`
- Question: `[sales_leader] Show pipeline health for 2017-Q2 in the East region with a stage breakdown.`
- Notes: Actor tag indicates the intended principal for the same governed question.

## 11. actor-variant-1

- Category: `actor-aware-variant`
- Expected outcome: `success`
- Question: `[sales_leader] Show the top 5 at-risk accounts in 2017-Q2 for the East region.`

## 12. actor-variant-2

- Category: `actor-aware-variant`
- Expected outcome: `success`
- Question: `[sales_analyst] Show the top 5 at-risk accounts in 2017-Q2 for the East region.`

## 13. actor-variant-3

- Category: `actor-aware-variant`
- Expected outcome: `success`
- Question: `[account_manager_east] Show the top 5 at-risk accounts in 2017-Q2 for the East region.`

## 14. actor-variant-4

- Category: `actor-aware-variant`
- Expected outcome: `restricted`
- Question: `[account_manager_east] Show the top 5 at-risk accounts in 2017-Q2 for the Central region.`

## 15. actor-variant-5

- Category: `actor-aware-variant`
- Expected outcome: `approval_required`
- Question: `[rev_ops_manager] Prepare follow-up tasks for the top 3 at-risk accounts in the East region for 2017-Q2.`

## 16. actor-variant-6

- Category: `actor-aware-variant`
- Expected outcome: `denied`
- Question: `[sales_analyst] Prepare follow-up tasks for the top 3 at-risk accounts in the East region for 2017-Q2.`

## 17. actor-variant-7

- Category: `actor-aware-variant`
- Expected outcome: `success`
- Question: `[sales_leader] Find lookalike accounts similar to Acme Corporation.`

## 18. actor-variant-8

- Category: `actor-aware-variant`
- Expected outcome: `denied`
- Question: `[sales_analyst] Find lookalike accounts similar to Acme Corporation.`

## 19. actor-variant-9

- Category: `actor-aware-variant`
- Expected outcome: `success`
- Question: `[sales_leader] Summarize firmographic context for Condax and Acme Corporation.`

## 20. actor-variant-10

- Category: `actor-aware-variant`
- Expected outcome: `success`
- Question: `[sales_analyst] Summarize firmographic context for Condax and Acme Corporation.`

## 21. actor-matrix-21

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_leader] Show pipeline health for 2017-Q2 in the Central region.`

## 22. actor-matrix-22

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_analyst] Show pipeline health for 2017-Q2 in the East region.`

## 23. actor-matrix-23

- Category: `actor-aware-matrix`
- Expected outcome: `restricted`
- Question: `[account_manager_east] Show pipeline health for 2017-Q2 in the West region.`

## 24. actor-matrix-24

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[rev_ops_manager] Show pipeline health for 2017-Q2 in the Central region.`

## 25. actor-matrix-25

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_leader] Show pipeline health for 2017-Q2 in the East region.`

## 26. actor-matrix-26

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_analyst] Show pipeline health for 2017-Q2 in the West region.`

## 27. actor-matrix-27

- Category: `actor-aware-matrix`
- Expected outcome: `restricted`
- Question: `[account_manager_east] Show pipeline health for 2017-Q2 in the Central region.`

## 28. actor-matrix-28

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[rev_ops_manager] Show pipeline health for 2017-Q2 in the East region.`

## 29. actor-matrix-29

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_leader] Show pipeline health for 2017-Q2 in the West region.`

## 30. actor-matrix-30

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_analyst] Show pipeline health for 2017-Q2 in the Central region.`

## 31. actor-matrix-31

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[account_manager_east] Show pipeline health for 2017-Q2 in the East region.`

## 32. actor-matrix-32

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[rev_ops_manager] Show pipeline health for 2017-Q2 in the West region.`

## 33. actor-matrix-33

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_leader] Show pipeline health for 2017-Q2 in the Central region.`

## 34. actor-matrix-34

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_analyst] Show pipeline health for 2017-Q2 in the East region.`

## 35. actor-matrix-35

- Category: `actor-aware-matrix`
- Expected outcome: `restricted`
- Question: `[account_manager_east] Show pipeline health for 2017-Q2 in the West region.`

## 36. actor-matrix-36

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[rev_ops_manager] Show pipeline health for 2017-Q2 in the Central region.`

## 37. actor-matrix-37

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_leader] Show pipeline health for 2017-Q2 in the East region.`

## 38. actor-matrix-38

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_analyst] Show pipeline health for 2017-Q2 in the West region.`

## 39. actor-matrix-39

- Category: `actor-aware-matrix`
- Expected outcome: `restricted`
- Question: `[account_manager_east] Show pipeline health for 2017-Q2 in the Central region.`

## 40. actor-matrix-40

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[rev_ops_manager] Show pipeline health for 2017-Q2 in the East region.`

## 41. actor-matrix-41

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_leader] Show pipeline health for 2017-Q2 in the West region.`

## 42. actor-matrix-42

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_analyst] Show pipeline health for 2017-Q2 in the Central region.`

## 43. actor-matrix-43

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[account_manager_east] Show pipeline health for 2017-Q2 in the East region.`

## 44. actor-matrix-44

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[rev_ops_manager] Show pipeline health for 2017-Q2 in the West region.`

## 45. actor-matrix-45

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_leader] Show pipeline health for 2017-Q2 in the Central region.`

## 46. actor-matrix-46

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_analyst] Show pipeline health for 2017-Q2 in the East region.`

## 47. actor-matrix-47

- Category: `actor-aware-matrix`
- Expected outcome: `restricted`
- Question: `[account_manager_east] Show pipeline health for 2017-Q2 in the West region.`

## 48. actor-matrix-48

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[rev_ops_manager] Show pipeline health for 2017-Q2 in the Central region.`

## 49. actor-matrix-49

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_leader] Show pipeline health for 2017-Q2 in the East region.`

## 50. actor-matrix-50

- Category: `actor-aware-matrix`
- Expected outcome: `success`
- Question: `[sales_analyst] Show pipeline health for 2017-Q2 in the West region.`
