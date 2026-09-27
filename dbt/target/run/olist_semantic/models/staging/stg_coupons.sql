
  
  create view "olist_dirty"."staging"."stg_coupons__dbt_tmp" as (
    -- Resolves: 11 spellings of 3 coupon-type concepts, and the 0.15-vs-15
-- scale ambiguity on percent coupons.
with src as (select * from "olist_dirty"."raw"."coupons"),

typed as (
    select
        *,
        lower(trim(coupon_type)) as _t,
        cast(discount_value as double) as _v
    from src
)

select
    trim(coupon_code)                                        as coupon_code,
    trim(campaign_name)                                      as campaign_name,
    campaign_description,

    case
        when _t in ('pct', 'percent', 'percentage', '%')          then 'PERCENT'
        when _t in ('fixed', 'brl', 'amount', 'fixed_amount')     then 'FIXED'
        when _t in ('freeship', 'free_shipping', 'frete')         then 'FREE_SHIPPING'
    end                                                      as coupon_type,

    -- one convention: always whole percent (15.0 means 15%)
    case
        when _t in ('pct', 'percent', 'percentage', '%')
        then round(case when _v <= 1 then _v * 100 else _v end, 2)
    end                                                      as discount_pct,

    case
        when _t in ('fixed', 'brl', 'amount', 'fixed_amount')
        then cast(_v as decimal(14,2))
    end                                                      as discount_fixed_brl,

    cast(min_order_value as decimal(14,2))                   as min_order_value,
    nullif(cast(max_discount_cap as decimal(14,2)), 0)       as max_discount_cap,
    
    coalesce(
        try_strptime(trim(valid_from), '%Y-%m-%d %H:%M:%S'),
        try_strptime(trim(valid_from), '%Y-%m-%dT%H:%M:%SZ'),
        try_strptime(trim(valid_from), '%d/%m/%Y %H:%M'),
        try_strptime(trim(valid_from), '%Y-%m-%d'),
        case
            when regexp_matches(trim(valid_from), '^[0-9]{9,11}$')
            then cast(to_timestamp(try_cast(trim(valid_from) as bigint)) at time zone 'UTC' as timestamp)
        end
    )
                             as valid_from,
    
    coalesce(
        try_strptime(trim(valid_to), '%Y-%m-%d %H:%M:%S'),
        try_strptime(trim(valid_to), '%Y-%m-%dT%H:%M:%SZ'),
        try_strptime(trim(valid_to), '%d/%m/%Y %H:%M'),
        try_strptime(trim(valid_to), '%Y-%m-%d'),
        case
            when regexp_matches(trim(valid_to), '^[0-9]{9,11}$')
            then cast(to_timestamp(try_cast(trim(valid_to) as bigint)) at time zone 'UTC' as timestamp)
        end
    )
                               as valid_to,
    lower(trim(is_active)) in ('y', '1', 'true')             as is_active,
    upper(trim(applies_to))                                  as applies_to,
    lower(trim(stackable)) = 'y'                             as is_stackable
from typed
  );
