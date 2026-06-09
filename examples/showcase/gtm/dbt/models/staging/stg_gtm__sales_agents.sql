select
    md5(sales_agent) as sales_agent_key,
    trim(sales_agent) as sales_agent_name,
    trim(manager) as manager_name,
    trim(regional_office) as regional_office
from {{ source('raw_gtm', 'sales_teams') }}
