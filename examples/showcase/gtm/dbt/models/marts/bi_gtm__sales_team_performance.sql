select
    engage_quarter,
    regional_office,
    manager_name,
    sum(opportunity_count) as opportunity_count,
    sum(open_opportunity_count) as open_opportunity_count,
    sum(won_opportunity_count) as won_opportunity_count,
    sum(lost_opportunity_count) as lost_opportunity_count,
    round(coalesce(sum(won_revenue), 0), 2) as won_revenue,
    round(coalesce(sum(open_pipeline_value), 0), 2) as open_pipeline_value,
    round(avg(average_open_risk_score), 2) as average_open_risk_score,
    round(avg(average_open_days), 2) as average_open_days
from {{ ref('mart_gtm__pipeline_health') }}
group by 1, 2, 3
