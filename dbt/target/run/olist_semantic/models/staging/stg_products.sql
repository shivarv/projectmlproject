
  
  create view "olist_dirty"."staging"."stg_products__dbt_tmp" as (
    select
    product_id,
    lower(trim(product_category_name))       as product_category_name,
    product_name_lenght                      as name_length,
    product_description_lenght               as description_length,
    product_photos_qty                       as photos_qty,
    product_weight_g                         as weight_g,
    product_length_cm                        as length_cm,
    product_height_cm                        as height_cm,
    product_width_cm                         as width_cm
from "olist_dirty"."raw"."products"
  );
