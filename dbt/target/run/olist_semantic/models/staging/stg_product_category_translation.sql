
  
  create view "olist_dirty"."staging"."stg_product_category_translation__dbt_tmp" as (
    select
    lower(trim(product_category_name))           as product_category_name,
    lower(trim(product_category_name_english))   as product_category_name_english
from "olist_dirty"."raw"."product_category_name_translation"
  );
