select
    account_name,
    sector,
    office_location,
    parent_company,
    revenue_band,
    employee_band,
    icp_fit,
    intent_signal,
    likely_buying_motion,
    enrichment_rationale
from {{ ref('mart_gtm__account_enrichment') }}
