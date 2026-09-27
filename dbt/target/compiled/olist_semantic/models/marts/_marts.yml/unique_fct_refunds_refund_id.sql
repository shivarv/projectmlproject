
    
    

select
    refund_id as unique_field,
    count(*) as n_records

from "olist_dirty"."marts"."fct_refunds"
where refund_id is not null
group by refund_id
having count(*) > 1


