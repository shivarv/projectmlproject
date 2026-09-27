
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    redemption_id as unique_field,
    count(*) as n_records

from "olist_dirty"."marts"."fct_coupon_redemptions"
where redemption_id is not null
group by redemption_id
having count(*) > 1



  
  
      
    ) dbt_internal_test