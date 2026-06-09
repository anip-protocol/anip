select
    engage_quarter,
    regional_office,
    manager_name,
    deal_stage,
    count(*) as opportunity_count,
    count(*) filter (where is_open) as open_opportunity_count,
    count(*) filter (where is_won) as won_opportunity_count,
    count(*) filter (where is_lost) as lost_opportunity_count,
    round(coalesce(sum(close_value) filter (where is_won), 0), 2) as won_revenue,
    round(coalesce(sum(coalesce(close_value, sales_price)) filter (where is_open), 0), 2) as open_pipeline_value,
    round(avg(risk_score) filter (where is_open), 2) as average_open_risk_score,
    round(avg(days_since_engage) filter (where is_open), 2) as average_open_days
from {{ ref('fct_gtm__opportunities') }}
group by 1, 2, 3, 4
