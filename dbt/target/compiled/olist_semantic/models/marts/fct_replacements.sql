-- Zero-revenue fulfilled shipments. Deliberately a SEPARATE fact so that
-- units_sold and AOV cannot accidentally absorb them.
select
    replacement_order_id,
    original_order_id,
    return_id,
    customer_id,
    product_id,
    seller_id,
    quantity_shipped,
    charged_to_customer,        -- always 0.00
    replacement_cogs,
    freight_absorbed,
    replacement_cogs + freight_absorbed as total_replacement_cost,
    cost_borne_by,
    replacement_status,
    shipped_at,
    delivered_at
from "olist_dirty"."staging"."stg_replacement_orders"