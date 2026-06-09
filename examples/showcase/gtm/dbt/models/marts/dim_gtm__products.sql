select
    product_key,
    product_name,
    product_series,
    sales_price
from {{ ref('stg_gtm__products') }}
