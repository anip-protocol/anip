with accounts as (
    select * from {{ ref('dim_gtm__accounts') }}
)

select
    account_name,
    sector,
    office_location,
    coalesce(subsidiary_of, 'independent') as parent_company,
    revenue_usd_millions,
    employees,
    case
        when revenue_usd_millions >= 3000 then 'enterprise'
        when revenue_usd_millions >= 1000 then 'mid_market'
        else 'commercial'
    end as revenue_band,
    case
        when employees >= 5000 then '5000_plus'
        when employees >= 2000 then '2000_to_4999'
        when employees >= 500 then '500_to_1999'
        else 'under_500'
    end as employee_band,
    case
        when sector in ('software', 'marketing', 'technolgy') and revenue_usd_millions >= 1000 then 'strong_fit'
        when sector in ('software', 'technolgy', 'medical') then 'qualified_fit'
        else 'conditional_fit'
    end as icp_fit,
    case
        when office_location = 'United States' and sector in ('software', 'technolgy', 'marketing') then 'high'
        when office_location = 'United States' then 'medium'
        else 'observed'
    end as intent_signal,
    case
        when sector in ('software', 'technolgy') then 'cloud_modernization'
        when sector = 'medical' then 'regulated_growth'
        when sector = 'retail' then 'commerce_efficiency'
        else 'general_expansion'
    end as likely_buying_motion,
    concat_ws(
        '|',
        sector,
        office_location,
        case
            when revenue_usd_millions >= 3000 then 'enterprise'
            when revenue_usd_millions >= 1000 then 'mid_market'
            else 'commercial'
        end,
        case
            when employees >= 5000 then '5000_plus'
            when employees >= 2000 then '2000_to_4999'
            when employees >= 500 then '500_to_1999'
            else 'under_500'
        end
    ) as lookalike_key,
    concat(
        'Sector=', sector,
        '; region=', office_location,
        '; revenue_band=',
        case
            when revenue_usd_millions >= 3000 then 'enterprise'
            when revenue_usd_millions >= 1000 then 'mid_market'
            else 'commercial'
        end,
        '; employee_band=',
        case
            when employees >= 5000 then '5000_plus'
            when employees >= 2000 then '2000_to_4999'
            when employees >= 500 then '500_to_1999'
            else 'under_500'
        end,
        '; fit=', 
        case
            when sector in ('software', 'marketing', 'technolgy') and revenue_usd_millions >= 1000 then 'strong_fit'
            when sector in ('software', 'technolgy', 'medical') then 'qualified_fit'
            else 'conditional_fit'
        end
    ) as enrichment_rationale
from accounts
