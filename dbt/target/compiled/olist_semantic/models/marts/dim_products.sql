select
    p.product_id,
    coalesce(t.product_category_name_english, p.product_category_name, 'unknown')
                                     as category,
    p.product_category_name          as category_pt,
    p.weight_g,
    p.length_cm,
    p.height_cm,
    p.width_cm,
    p.photos_qty
from "olist_dirty"."staging"."stg_products" p
left join "olist_dirty"."staging"."stg_product_category_translation" t
       on t.product_category_name = p.product_category_name