-- Grain is customer_unique_id (the PERSON), not customer_id (which Olist
-- issues fresh per order). 99,441 order-scoped keys collapse to 96,096 people.
with c as (select * from {{ ref('stg_customers') }}),
     o as (select * from {{ ref('stg_orders') }})

select
    c.customer_unique_id,
    count(distinct o.order_id)                          as lifetime_order_count,
    min(o.purchased_at)                                 as first_purchase_at,
    max(o.purchased_at)                                 as last_purchase_at,
    arg_max(c.customer_state,   o.purchased_at)         as customer_state,
    arg_max(c.customer_city,    o.purchased_at)         as customer_city,
    arg_max(c.zip_code_prefix,  o.purchased_at)         as zip_code_prefix,
    count(distinct o.order_id) > 1                      as is_repeat_customer
from c
join o on o.customer_id = c.customer_id
group by 1
