select
    account_key,
    account_name,
    sector,
    year_established,
    revenue_usd_millions,
    employees,
    office_location,
    subsidiary_of
from {{ ref('stg_gtm__accounts') }}
