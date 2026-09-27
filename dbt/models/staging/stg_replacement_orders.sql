-- Free replacement shipments: real fulfilled units at zero revenue, carrying
-- real COGS. Kept in a separate model so they can never be mistaken for sales.
select
    replacement_order_id,
    original_order_id,
    return_id,
    customer_id,
    product_id,
    seller_id,
    cast(quantity_shipped as integer)                    as quantity_shipped,
    cast(charged_to_customer as decimal(14,2))           as charged_to_customer,
    {{ parse_money('replacement_cogs') }}                as replacement_cogs,
    {{ parse_money('freight_absorbed') }}                as freight_absorbed,
    upper(trim(cost_borne_by))                           as cost_borne_by,
    upper(trim(replacement_status))                      as replacement_status,
    {{ parse_ts('shipped_at') }}                         as shipped_at,
    {{ parse_ts('delivered_at') }}                       as delivered_at
from {{ source('raw', 'replacement_orders') }}
