
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select lifetime_order_count
from "olist_dirty"."marts"."dim_customers"
where lifetime_order_count is null



  
  
      
    ) dbt_internal_test