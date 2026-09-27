
  
  create view "olist_dirty"."staging"."stg_order_items__dbt_tmp" as (
    select
    order_id,
    order_item_id,
    product_id,
    seller_id,
    shipping_limit_date                      as shipping_limit_at,
    cast(price as decimal(14,2))             as item_price,
    cast(freight_value as decimal(14,2))     as freight_value
from "olist_dirty"."raw"."order_items"
  );
