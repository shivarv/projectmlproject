
    

    create  table
      "olist_dirty"."marts"."dim_sellers__dbt_tmp"
  
    
    as (
      select
    seller_id,
    seller_city,
    seller_state,
    zip_code_prefix
from "olist_dirty"."staging"."stg_sellers"
    );
    
  