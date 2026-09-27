
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select redemption_id
from "olist_dirty"."marts"."fct_coupon_redemptions"
where redemption_id is null



  
  
      
    ) dbt_internal_test