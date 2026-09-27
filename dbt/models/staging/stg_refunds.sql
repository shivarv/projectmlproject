-- Resolves: the sign trap (1,249 of 3,624 rows stored negative for the same
-- semantic event) and status casing. Settlement is made explicit so that
-- pending/failed/reversed refunds can never be silently deducted.
with src as (select * from {{ source('raw', 'refunds') }}),

parsed as (
    select
        refund_id,
        order_id,
        return_id,
        upper(trim(refund_type))                         as refund_type,
        abs({{ parse_money('refund_amount') }})          as refund_amount,
        upper(trim(refund_reason))                       as refund_reason,
        lower(trim(refund_status))                       as _status,
        upper(trim(refund_method))                       as refund_method,
        {{ parse_ts('requested_at') }}                   as requested_at,
        {{ parse_ts('processed_at') }}                   as processed_at,
        gateway_reference
    from src
)

select
    * exclude (_status),
    upper(_status)                                       as refund_status,
    (_status = 'processed')                              as is_settled,
    case when _status = 'processed' then processed_at end as settled_at
from parsed
