select
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    i.shipping_limit_at,
    i.item_price,
    i.freight_value,
    i.item_price + i.freight_value  as gross_item_value
from "olist_dirty"."staging"."stg_order_items" i