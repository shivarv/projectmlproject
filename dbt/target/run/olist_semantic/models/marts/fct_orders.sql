
    

    create  table
      "olist_dirty"."marts"."fct_orders__dbt_tmp"
  
    
    as (
      -- One row per order, with money and review context already collapsed to the
-- order grain so downstream joins cannot fan out.
with o as (select * from "olist_dirty"."staging"."stg_orders"),
     c as (select * from "olist_dirty"."staging"."stg_customers"),
     i as (
        select
            order_id,
            sum(item_price)             as merchandise_value,
            sum(freight_value)          as freight_value,
            count(*)                    as item_count,
            count(distinct seller_id)   as seller_count
        from "olist_dirty"."staging"."stg_order_items"
        group by 1
     ),
     p as (select * from "olist_dirty"."marts"."fct_payments"),
     r as (select * from "olist_dirty"."marts"."fct_order_reviews")

select
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    c.customer_state,
    c.customer_city,
    c.zip_code_prefix,
    o.order_status,

    -- all five dates kept and named, so "when" is never implicit
    o.purchased_at,
    o.approved_at,
    o.shipped_at,
    o.delivered_at,
    o.estimated_delivery_at,
    case when o.order_status = 'delivered' then o.delivered_at end  as recognized_at,

    o.order_status = 'delivered'                                    as is_delivered,
    o.order_status in ('canceled', 'unavailable')                   as is_canceled,
    case
        when o.delivered_at is not null and o.estimated_delivery_at is not null
        then o.delivered_at > o.estimated_delivery_at
    end                                                             as is_late,
    case
        when o.delivered_at is not null
        then date_diff('day', o.purchased_at, o.delivered_at)
    end                                                             as delivery_days,

    coalesce(i.merchandise_value, 0)                                as merchandise_value,
    coalesce(i.freight_value, 0)                                    as freight_value,
    coalesce(i.merchandise_value, 0) + coalesce(i.freight_value, 0) as gross_order_value,
    coalesce(i.item_count, 0)                                       as item_count,
    coalesce(i.seller_count, 0)                                     as seller_count,

    p.amount_paid,
    p.primary_payment_type,
    r.review_score,
    coalesce(r.review_count, 0)                                     as review_count
from o
left join c on c.customer_id = o.customer_id
left join i on i.order_id    = o.order_id
left join p on p.order_id    = o.order_id
left join r on r.order_id    = o.order_id
    );
    
  