
    
    

select
    seller_id as unique_field,
    count(*) as n_records

from "olist_dirty"."marts"."dim_sellers"
where seller_id is not null
group by seller_id
having count(*) > 1


