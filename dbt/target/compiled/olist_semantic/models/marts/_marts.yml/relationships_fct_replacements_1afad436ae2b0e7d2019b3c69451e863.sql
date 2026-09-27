
    
    

with child as (
    select return_id as from_field
    from "olist_dirty"."marts"."fct_replacements"
    where return_id is not null
),

parent as (
    select return_id as to_field
    from "olist_dirty"."marts"."fct_returns"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


