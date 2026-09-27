
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select item_price
from "olist_dirty"."marts"."fct_order_items"
where item_price is null



  
  
      
    ) dbt_internal_test