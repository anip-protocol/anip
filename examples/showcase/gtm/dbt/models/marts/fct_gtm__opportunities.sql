with joined as (
    select
        o.opportunity_key,
        o.opportunity_id,
        o.sales_agent_name,
        sa.sales_agent_key,
        sa.manager_name,
        sa.regional_office,
        o.product_name,
        p.product_key,
        p.product_series,
        p.sales_price,
        o.account_name,
        a.account_key,
        a.sector,
        a.revenue_usd_millions,
        a.employees,
        a.office_location,
        o.deal_stage,
        o.engage_date,
        o.close_date,
        o.close_value,
        o.is_closed,
        o.is_open,
        o.is_won,
        o.is_lost,
        o.days_since_engage,
        o.days_to_close,
        o.engage_quarter,
        o.close_quarter,
        case
            when o.is_closed then 0.0
            else round(
                (
                    case
                        when o.deal_stage = 'Prospecting' then 0.82
                        when o.deal_stage = 'Engaging' then 0.68
                        else 0.50
                    end
                    + case when o.days_since_engage >= 120 then 0.18 else 0.0 end
                    + case when coalesce(a.revenue_usd_millions, 0) < 300 then 0.08 else 0.0 end
                )::numeric,
                2
            )
        end as risk_score
    from {{ ref('stg_gtm__opportunities') }} o
    left join {{ ref('stg_gtm__sales_agents') }} sa
        on o.sales_agent_name = sa.sales_agent_name
    left join {{ ref('stg_gtm__products') }} p
        on o.product_name = p.product_name
    left join {{ ref('stg_gtm__accounts') }} a
        on o.account_name = a.account_name
)
select * from joined
