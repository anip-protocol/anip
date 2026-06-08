select
    sales_agent_key,
    sales_agent_name,
    manager_name,
    regional_office
from {{ ref('stg_gtm__sales_agents') }}
