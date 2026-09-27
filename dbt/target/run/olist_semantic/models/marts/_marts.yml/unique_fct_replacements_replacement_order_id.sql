
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    replacement_order_id as unique_field,
    count(*) as n_records

from "olist_dirty"."marts"."fct_replacements"
where replacement_order_id is not null
group by replacement_order_id
having count(*) > 1



  
  
      
    ) dbt_internal_test