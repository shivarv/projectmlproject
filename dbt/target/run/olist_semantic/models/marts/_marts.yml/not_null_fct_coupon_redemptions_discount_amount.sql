
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select discount_amount
from "olist_dirty"."marts"."fct_coupon_redemptions"
where discount_amount is null



  
  
      
    ) dbt_internal_test