select
    seller_id,
    seller_city,
    seller_state,
    zip_code_prefix
from {{ ref('stg_sellers') }}
