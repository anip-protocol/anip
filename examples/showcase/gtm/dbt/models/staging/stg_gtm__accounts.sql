select
    md5(account) as account_key,
    trim(account) as account_name,
    case
        when lower(trim(sector)) = 'technolgy' then 'technology'
        else lower(trim(sector))
    end as sector,
    year_established,
    revenue::numeric(18, 2) as revenue_usd_millions,
    employees,
    case
        when trim(office_location) = 'Philipines' then 'Philippines'
        else trim(office_location)
    end as office_location,
    nullif(trim(subsidiary_of), '') as subsidiary_of
from {{ source('raw_gtm', 'accounts') }}
