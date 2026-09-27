
  
  create view "olist_dirty"."staging"."stg_order_returns__dbt_tmp" as (
    -- Resolves: bilingual/free-text reason codes collapsed to 8 canonical values,
-- status casing, and 0.8% clock-skew rows where resolved_at precedes requested_at.
with src as (select * from "olist_dirty"."raw"."order_returns"),

parsed as (
    select
        return_id,
        order_id,
        cast(order_item_id as integer)                   as order_item_id,
        product_id,
        seller_id,
        customer_id,
        lower(trim(return_reason_code))                  as _reason,
        lower(trim(return_status))                       as _status,
        upper(trim(resolution))                          as resolution,
        cast(quantity_returned as integer)               as quantity_returned,
        
    cast(
        case
            when item_price_at_purchase is null then null
            when position(',' in replace(replace(item_price_at_purchase, 'R$', ''), ' ', '')) > 0
                then replace(replace(replace(replace(item_price_at_purchase, 'R$', ''), ' ', ''), '.', ''), ',', '.')
            else replace(replace(item_price_at_purchase, 'R$', ''), ' ', '')
        end
    as decimal(14,2))
      as item_price_at_purchase,
        
    cast(
        case
            when freight_at_purchase is null then null
            when position(',' in replace(replace(freight_at_purchase, 'R$', ''), ' ', '')) > 0
                then replace(replace(replace(replace(freight_at_purchase, 'R$', ''), ' ', ''), '.', ''), ',', '.')
            else replace(replace(freight_at_purchase, 'R$', ''), ' ', '')
        end
    as decimal(14,2))
         as freight_at_purchase,
        
    coalesce(
        try_strptime(trim(requested_at), '%Y-%m-%d %H:%M:%S'),
        try_strptime(trim(requested_at), '%Y-%m-%dT%H:%M:%SZ'),
        try_strptime(trim(requested_at), '%d/%m/%Y %H:%M'),
        try_strptime(trim(requested_at), '%Y-%m-%d'),
        case
            when regexp_matches(trim(requested_at), '^[0-9]{9,11}$')
            then cast(to_timestamp(try_cast(trim(requested_at) as bigint)) at time zone 'UTC' as timestamp)
        end
    )
                   as requested_at,
        
    coalesce(
        try_strptime(trim(received_at), '%Y-%m-%d %H:%M:%S'),
        try_strptime(trim(received_at), '%Y-%m-%dT%H:%M:%SZ'),
        try_strptime(trim(received_at), '%d/%m/%Y %H:%M'),
        try_strptime(trim(received_at), '%Y-%m-%d'),
        case
            when regexp_matches(trim(received_at), '^[0-9]{9,11}$')
            then cast(to_timestamp(try_cast(trim(received_at) as bigint)) at time zone 'UTC' as timestamp)
        end
    )
                    as received_at,
        
    coalesce(
        try_strptime(trim(resolved_at), '%Y-%m-%d %H:%M:%S'),
        try_strptime(trim(resolved_at), '%Y-%m-%dT%H:%M:%SZ'),
        try_strptime(trim(resolved_at), '%d/%m/%Y %H:%M'),
        try_strptime(trim(resolved_at), '%Y-%m-%d'),
        case
            when regexp_matches(trim(resolved_at), '^[0-9]{9,11}$')
            then cast(to_timestamp(try_cast(trim(resolved_at) as bigint)) at time zone 'UTC' as timestamp)
        end
    )
                    as resolved_at,
        inspection_notes
    from src
)

select
    * exclude (_reason, _status),

    case
        when _reason in ('damaged', 'damaged_in_transit', 'produto danificado')  then 'DAMAGED_IN_TRANSIT'
        when _reason in ('defective', 'defeito')                                 then 'DEFECTIVE'
        when _reason in ('wrong_item', 'wrong item', 'wrong-item', 'item_errado') then 'WRONG_ITEM'
        when _reason in ('not_as_described', 'nao conforme anuncio')             then 'NOT_AS_DESCRIBED'
        when _reason in ('missing_parts', 'faltando pecas')                      then 'MISSING_PARTS'
        when _reason in ('size_fit', 'size/fit', 'tamanho')                      then 'SIZE_FIT'
        when _reason in ('late_delivery', 'late', 'atraso na entrega')           then 'LATE_DELIVERY'
        when _reason in ('no_longer_wanted', 'no longer wanted', 'changed_mind', 'arrependimento')
                                                                                 then 'NO_LONGER_WANTED'
    end                                                  as return_reason,

    case
        when _status in ('completed', 'closed')          then 'COMPLETED'
        when _status = 'approved'                        then 'APPROVED'
        when _status in ('rejected', 'denied')           then 'REJECTED'
        when _status in ('requested', 'open')            then 'REQUESTED'
        when _status in ('in_transit', 'shipping_back')  then 'IN_TRANSIT'
    end                                                  as return_status,

    -- explicit flag rather than silently propagating a negative duration
    (resolved_at is not null and resolved_at < requested_at) as has_timestamp_inconsistency,

    case
        when resolved_at is not null and resolved_at >= requested_at
        then date_diff('day', requested_at, resolved_at)
    end                                                  as resolution_days
from parsed
  );
