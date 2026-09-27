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
    
    cast(
        case
            when replacement_cogs is null then null
            when position(',' in replace(replace(replacement_cogs, 'R$', ''), ' ', '')) > 0
                then replace(replace(replace(replace(replacement_cogs, 'R$', ''), ' ', ''), '.', ''), ',', '.')
            else replace(replace(replacement_cogs, 'R$', ''), ' ', '')
        end
    as decimal(14,2))
                as replacement_cogs,
    
    cast(
        case
            when freight_absorbed is null then null
            when position(',' in replace(replace(freight_absorbed, 'R$', ''), ' ', '')) > 0
                then replace(replace(replace(replace(freight_absorbed, 'R$', ''), ' ', ''), '.', ''), ',', '.')
            else replace(replace(freight_absorbed, 'R$', ''), ' ', '')
        end
    as decimal(14,2))
                as freight_absorbed,
    upper(trim(cost_borne_by))                           as cost_borne_by,
    upper(trim(replacement_status))                      as replacement_status,
    
    coalesce(
        try_strptime(trim(shipped_at), '%Y-%m-%d %H:%M:%S'),
        try_strptime(trim(shipped_at), '%Y-%m-%dT%H:%M:%SZ'),
        try_strptime(trim(shipped_at), '%d/%m/%Y %H:%M'),
        try_strptime(trim(shipped_at), '%Y-%m-%d'),
        case
            when regexp_matches(trim(shipped_at), '^[0-9]{9,11}$')
            then cast(to_timestamp(try_cast(trim(shipped_at) as bigint)) at time zone 'UTC' as timestamp)
        end
    )
                         as shipped_at,
    
    coalesce(
        try_strptime(trim(delivered_at), '%Y-%m-%d %H:%M:%S'),
        try_strptime(trim(delivered_at), '%Y-%m-%dT%H:%M:%SZ'),
        try_strptime(trim(delivered_at), '%d/%m/%Y %H:%M'),
        try_strptime(trim(delivered_at), '%Y-%m-%d'),
        case
            when regexp_matches(trim(delivered_at), '^[0-9]{9,11}$')
            then cast(to_timestamp(try_cast(trim(delivered_at) as bigint)) at time zone 'UTC' as timestamp)
        end
    )
                       as delivered_at
from "olist_dirty"."raw"."replacement_orders"