
  
  create view "olist_dirty"."staging"."stg_refunds__dbt_tmp" as (
    -- Resolves: the sign trap (1,249 of 3,624 rows stored negative for the same
-- semantic event) and status casing. Settlement is made explicit so that
-- pending/failed/reversed refunds can never be silently deducted.
with src as (select * from "olist_dirty"."raw"."refunds"),

parsed as (
    select
        refund_id,
        order_id,
        return_id,
        upper(trim(refund_type))                         as refund_type,
        abs(
    cast(
        case
            when refund_amount is null then null
            when position(',' in replace(replace(refund_amount, 'R$', ''), ' ', '')) > 0
                then replace(replace(replace(replace(refund_amount, 'R$', ''), ' ', ''), '.', ''), ',', '.')
            else replace(replace(refund_amount, 'R$', ''), ' ', '')
        end
    as decimal(14,2))
)          as refund_amount,
        upper(trim(refund_reason))                       as refund_reason,
        lower(trim(refund_status))                       as _status,
        upper(trim(refund_method))                       as refund_method,
        
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
        try_strptime(trim(processed_at), '%Y-%m-%d %H:%M:%S'),
        try_strptime(trim(processed_at), '%Y-%m-%dT%H:%M:%SZ'),
        try_strptime(trim(processed_at), '%d/%m/%Y %H:%M'),
        try_strptime(trim(processed_at), '%Y-%m-%d'),
        case
            when regexp_matches(trim(processed_at), '^[0-9]{9,11}$')
            then cast(to_timestamp(try_cast(trim(processed_at) as bigint)) at time zone 'UTC' as timestamp)
        end
    )
                   as processed_at,
        gateway_reference
    from src
)

select
    * exclude (_status),
    upper(_status)                                       as refund_status,
    (_status = 'processed')                              as is_settled,
    case when _status = 'processed' then processed_at end as settled_at
from parsed
  );
