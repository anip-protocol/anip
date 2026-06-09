select
    engage_quarter,
    regional_office,
    deal_stage,
    count(*) filter (where is_open) as open_opportunity_count,
    round(coalesce(sum(coalesce(close_value, sales_price)) filter (where is_open), 0), 2) as open_pipeline_value,
    round(
        sum(
            case
                when is_open and deal_stage = 'Prospecting' then coalesce(close_value, sales_price) * 0.30
                when is_open and deal_stage = 'Engaging' then coalesce(close_value, sales_price) * 0.60
                else 0
            end
        ),
        2
    ) as likely_revenue,
    round(
        sum(
            case
                when is_open and deal_stage = 'Prospecting' then coalesce(close_value, sales_price) * 0.55
                when is_open and deal_stage = 'Engaging' then coalesce(close_value, sales_price) * 0.85
                else 0
            end
        ),
        2
    ) as best_case_revenue,
    round(
        sum(
            case
                when is_open and deal_stage = 'Prospecting'
                    then coalesce(close_value, sales_price) * 0.30 * greatest(0.45, 1.15 - coalesce(risk_score, 0))
                when is_open and deal_stage = 'Engaging'
                    then coalesce(close_value, sales_price) * 0.60 * greatest(0.45, 1.15 - coalesce(risk_score, 0))
                else 0
            end
        ),
        2
    ) as risk_adjusted_revenue,
    round(avg(risk_score) filter (where is_open), 2) as average_open_risk_score
from {{ ref('fct_gtm__opportunities') }}
group by 1, 2, 3
