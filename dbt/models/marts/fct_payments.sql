-- Pre-aggregated to ONE row per order. raw.order_payments has 2,843 orders
-- with multiple instalment rows; joining it at row grain double-counts revenue.
select
    order_id,
    sum(payment_value)                        as amount_paid,
    count(*)                                  as payment_row_count,
    max(payment_installments)                 as max_installments,
    arg_max(payment_type, payment_value)      as primary_payment_type,
    count(distinct payment_type)              as payment_type_count
from {{ ref('stg_order_payments') }}
group by 1
