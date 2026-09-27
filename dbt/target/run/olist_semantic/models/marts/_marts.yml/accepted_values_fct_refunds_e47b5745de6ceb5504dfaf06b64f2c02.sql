
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        refund_status as value_field,
        count(*) as n_records

    from "olist_dirty"."marts"."fct_refunds"
    group by refund_status

)

select *
from all_values
where value_field not in (
    'PROCESSED','PENDING','FAILED','REVERSED'
)



  
  
      
    ) dbt_internal_test