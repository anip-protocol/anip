select
    md5(product) as product_key,
    trim(product) as product_name,
    trim(series) as product_series,
    sales_price::numeric(18, 2) as sales_price
from {{ source('raw_gtm', 'products') }}
