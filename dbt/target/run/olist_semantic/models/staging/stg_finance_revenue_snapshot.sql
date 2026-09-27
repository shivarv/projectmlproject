
  
  create view "olist_dirty"."staging"."stg_finance_revenue_snapshot__dbt_tmp" as (
    -- Parsed for completeness ONLY. This export is known-stale (cut off
-- 2018-07-01, missing 12,824 orders) and double-counts duplicate redemptions.
-- It is deliberately never promoted to marts. See DATA.md.
select
    order_id,
    cast(snapshot_date as date)                          as snapshot_date,
    currency,
    cast(gross_merchandise_value as decimal(14,2))       as gross_merchandise_value,
    cast(freight_revenue as decimal(14,2))               as freight_revenue,
    cast(discount_total as decimal(14,2))                as discount_total,
    cast(refund_total as decimal(14,2))                  as refund_total,
    cast(net_revenue as decimal(14,2))                   as net_revenue,
    source_system
from "olist_dirty"."raw"."finance_order_revenue_snapshot"
  );
