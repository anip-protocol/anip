# Data

This directory holds the Phase 1 dataset bootstrap for the GTM showcase.

## Phase 1 anchor dataset

- Maven Analytics CRM Sales Opportunities
- mirrored from a public GitHub repository for reproducible local setup
- four source tables:
  - `accounts`
  - `products`
  - `sales_pipeline`
  - `sales_teams`

## Layout

- `raw/maven/`
  - committed CSV seed data for the Phase 1 pipeline loop
- `init/`
  - deterministic Postgres bootstrap SQL

## Notes

- `sales_pipeline.csv` contains `8,800` opportunity rows
- the staging/modeling layer intentionally fixes a small number of source inconsistencies, such as:
  - `GTXPro` in the pipeline table vs `GTX Pro` in the products table
  - a few spelling inconsistencies in sector and office location values
