select
    lower(trim(product_category_name))           as product_category_name,
    lower(trim(product_category_name_english))   as product_category_name_english
from "olist_dirty"."raw"."product_category_name_translation"