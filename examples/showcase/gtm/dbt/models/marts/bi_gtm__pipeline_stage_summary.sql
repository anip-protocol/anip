select
    engage_quarter,
    regional_office,
    manager_name,
    deal_stage,
    opportunity_count,
    open_opportunity_count,
    won_opportunity_count,
    lost_opportunity_count,
    won_revenue,
    open_pipeline_value,
    average_open_risk_score,
    average_open_days
from {{ ref('mart_gtm__pipeline_health') }}
