
    
    

with all_values as (

    select
        refund_type as value_field,
        count(*) as n_records

    from "olist_dirty"."marts"."fct_refunds"
    group by refund_type

)

select *
from all_values
where value_field not in (
    'FULL','PARTIAL','SHIPPING_ONLY','GOODWILL'
)


