select
    refund_id,
    order_id,
    return_id,
    refund_type,
    refund_amount,          -- always positive
    refund_reason,
    refund_status,
    refund_method,
    is_settled,
    requested_at,
    processed_at,
    settled_at,             -- null unless actually settled
    gateway_reference
from "olist_dirty"."staging"."stg_refunds"