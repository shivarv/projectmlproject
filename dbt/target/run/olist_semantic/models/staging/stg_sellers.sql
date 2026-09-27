
  
  create view "olist_dirty"."staging"."stg_sellers__dbt_tmp" as (
    select
    seller_id,
    seller_zip_code_prefix                   as zip_code_prefix,
    lower(trim(seller_city))               as seller_city,
    upper(trim(seller_state))                as seller_state
from "olist_dirty"."raw"."sellers"
  );
