
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select return_status
from "olist_dirty"."marts"."fct_returns"
where return_status is null



  
  
      
    ) dbt_internal_test