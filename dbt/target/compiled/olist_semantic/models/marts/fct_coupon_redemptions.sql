-- Deduped upstream. Orphan coupon codes (243 LEGACY* rows absent from the
-- coupon master) are RETAINED via LEFT JOIN and flagged, so discount totals
-- stay correct instead of silently shrinking.
select
    red.redemption_id,
    red.order_id,
    red.customer_id,
    red.coupon_code,
    red.discount_amount,
    red.discount_applies_to,
    red.redeemed_at,
    red.channel,
    cp.campaign_name,
    cp.coupon_type,
    cp.discount_pct,
    cp.discount_fixed_brl,
    cp.coupon_code is null              as is_orphan_coupon
from "olist_dirty"."staging"."stg_order_coupons" red
left join "olist_dirty"."staging"."stg_coupons" cp on cp.coupon_code = red.coupon_code