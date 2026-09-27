-- Resolves: 306 byte-identical duplicate rows from an ETL replay.
-- Orphan coupon_codes are PRESERVED (not dropped) so redemption totals stay
-- correct; marts join to coupons with a LEFT JOIN.
with deduped as (
    select
        *,
        row_number() over (partition by redemption_id order by order_id) as _rn
    from {{ source('raw', 'order_coupons') }}
)

select
    redemption_id,
    order_id,
    customer_id,
    trim(coupon_code)                                    as coupon_code,
    {{ parse_money('discount_amount_applied') }}         as discount_amount,
    upper(trim(discount_applies_to))                     as discount_applies_to,
    {{ parse_ts('redeemed_at') }}                        as redeemed_at,
    upper(trim(channel))                                 as channel
from deduped
where _rn = 1
