select
    engage_quarter,
    regional_office,
    manager_name,
    product_name,
    deal_stage,
    count(*) filter (where is_open) as open_opportunity_count,
    round(sum(coalesce(close_value, sales_price)) filter (where is_open), 2) as open_pipeline_value,
    round(avg(days_since_engage) filter (where is_open), 2) as average_open_days,
    round(avg(risk_score) filter (where is_open), 2) as average_open_risk_score
from {{ ref('fct_gtm__opportunities') }}
group by 1, 2, 3, 4, 5
having count(*) filter (where is_open) > 0
