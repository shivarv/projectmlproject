select
    customer_id,                               -- order-scoped key, NOT a person
    customer_unique_id,                        -- the actual person
    customer_zip_code_prefix                 as zip_code_prefix,
    lower(trim(customer_city))             as customer_city,
    upper(trim(customer_state))              as customer_state
from "olist_dirty"."raw"."customers"