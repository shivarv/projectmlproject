
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        resolution as value_field,
        count(*) as n_records

    from "olist_dirty"."marts"."fct_returns"
    group by resolution

)

select *
from all_values
where value_field not in (
    'REFUND','REPLACEMENT','STORE_CREDIT','REJECTED'
)



  
  
      
    ) dbt_internal_test