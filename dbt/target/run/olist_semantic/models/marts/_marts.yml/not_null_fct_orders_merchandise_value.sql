
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select merchandise_value
from "olist_dirty"."marts"."fct_orders"
where merchandise_value is null



  
  
      
    ) dbt_internal_test