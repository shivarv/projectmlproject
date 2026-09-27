
    
    

with all_values as (

    select
        order_status as value_field,
        count(*) as n_records

    from "olist_dirty"."marts"."fct_orders"
    group by order_status

)

select *
from all_values
where value_field not in (
    'delivered','shipped','canceled','unavailable','invoiced','processing','created','approved'
)


