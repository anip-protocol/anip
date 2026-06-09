select
    engage_quarter,
    regional_office,
    account_name,
    count(*) filter (where is_open) as open_opportunity_count,
    round(sum(coalesce(close_value, sales_price)) filter (where is_open), 2) as open_pipeline_value,
    round(avg(risk_score) filter (where is_open), 2) as average_risk_score,
    max(days_since_engage) filter (where is_open) as max_days_open,
    string_agg(distinct sales_agent_name, ', ' order by sales_agent_name) filter (where is_open) as sales_agents
from {{ ref('fct_gtm__opportunities') }}
where account_name is not null
  and trim(account_name) <> ''
group by 1, 2, 3
having count(*) filter (where is_open) > 0
