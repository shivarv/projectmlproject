
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        return_reason as value_field,
        count(*) as n_records

    from "olist_dirty"."marts"."fct_returns"
    group by return_reason

)

select *
from all_values
where value_field not in (
    'DAMAGED_IN_TRANSIT','DEFECTIVE','WRONG_ITEM','NOT_AS_DESCRIBED','MISSING_PARTS','SIZE_FIT','LATE_DELIVERY','NO_LONGER_WANTED'
)



  
  
      
    ) dbt_internal_test