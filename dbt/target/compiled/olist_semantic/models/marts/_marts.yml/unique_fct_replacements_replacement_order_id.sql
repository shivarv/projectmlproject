
    
    

select
    replacement_order_id as unique_field,
    count(*) as n_records

from "olist_dirty"."marts"."fct_replacements"
where replacement_order_id is not null
group by replacement_order_id
having count(*) > 1


