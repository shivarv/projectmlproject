
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select original_order_id
from "olist_dirty"."marts"."fct_replacements"
where original_order_id is null



  
  
      
    ) dbt_internal_test