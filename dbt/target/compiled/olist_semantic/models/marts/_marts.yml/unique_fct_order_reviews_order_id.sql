
    
    

select
    order_id as unique_field,
    count(*) as n_records

from "olist_dirty"."marts"."fct_order_reviews"
where order_id is not null
group by order_id
having count(*) > 1


