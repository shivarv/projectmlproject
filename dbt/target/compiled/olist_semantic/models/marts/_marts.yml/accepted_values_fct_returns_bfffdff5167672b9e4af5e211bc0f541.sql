
    
    

with all_values as (

    select
        return_status as value_field,
        count(*) as n_records

    from "olist_dirty"."marts"."fct_returns"
    group by return_status

)

select *
from all_values
where value_field not in (
    'COMPLETED','APPROVED','REJECTED','REQUESTED','IN_TRANSIT'
)


