with base as (
    select
        trim(opportunity_id) as opportunity_id,
        trim(sales_agent) as sales_agent_name,
        case
            when trim(product) = 'GTXPro' then 'GTX Pro'
            else trim(product)
        end as product_name,
        nullif(trim(account), '') as account_name,
        trim(deal_stage) as deal_stage,
        engage_date,
        close_date,
        close_value::numeric(18, 2) as close_value
    from {{ source('raw_gtm', 'sales_pipeline') }}
),
anchored as (
    select
        *,
        max(coalesce(close_date, engage_date)) over () as dataset_reference_date
    from base
)
select
    opportunity_id,
    md5(opportunity_id) as opportunity_key,
    sales_agent_name,
    product_name,
    account_name,
    deal_stage,
    engage_date,
    close_date,
    close_value,
    dataset_reference_date,
    case when deal_stage in ('Won', 'Lost') then true else false end as is_closed,
    case when deal_stage = 'Won' then true else false end as is_won,
    case when deal_stage = 'Lost' then true else false end as is_lost,
    case when deal_stage in ('Prospecting', 'Engaging') then true else false end as is_open,
    (dataset_reference_date - engage_date) as days_since_engage,
    case
        when close_date is not null then (close_date - engage_date)
        else null
    end as days_to_close,
    concat(extract(year from engage_date)::int, '-Q', extract(quarter from engage_date)::int) as engage_quarter,
    case
        when close_date is not null then concat(extract(year from close_date)::int, '-Q', extract(quarter from close_date)::int)
        else null
    end as close_quarter
from anchored
