
  
  create view "olist_dirty"."staging"."stg_order_coupons__dbt_tmp" as (
    -- Resolves: 306 byte-identical duplicate rows from an ETL replay.
-- Orphan coupon_codes are PRESERVED (not dropped) so redemption totals stay
-- correct; marts join to coupons with a LEFT JOIN.
with deduped as (
    select
        *,
        row_number() over (partition by redemption_id order by order_id) as _rn
    from "olist_dirty"."raw"."order_coupons"
)

select
    redemption_id,
    order_id,
    customer_id,
    trim(coupon_code)                                    as coupon_code,
    
    cast(
        case
            when discount_amount_applied is null then null
            when position(',' in replace(replace(discount_amount_applied, 'R$', ''), ' ', '')) > 0
                then replace(replace(replace(replace(discount_amount_applied, 'R$', ''), ' ', ''), '.', ''), ',', '.')
            else replace(replace(discount_amount_applied, 'R$', ''), ' ', '')
        end
    as decimal(14,2))
         as discount_amount,
    upper(trim(discount_applies_to))                     as discount_applies_to,
    
    coalesce(
        try_strptime(trim(redeemed_at), '%Y-%m-%d %H:%M:%S'),
        try_strptime(trim(redeemed_at), '%Y-%m-%dT%H:%M:%SZ'),
        try_strptime(trim(redeemed_at), '%d/%m/%Y %H:%M'),
        try_strptime(trim(redeemed_at), '%Y-%m-%d'),
        case
            when regexp_matches(trim(redeemed_at), '^[0-9]{9,11}$')
            then cast(to_timestamp(try_cast(trim(redeemed_at) as bigint)) at time zone 'UTC' as timestamp)
        end
    )
                        as redeemed_at,
    upper(trim(channel))                                 as channel
from deduped
where _rn = 1
  );
