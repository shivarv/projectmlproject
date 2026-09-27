select
    order_id,
    payment_sequential,
    lower(trim(payment_type))                    as payment_type,
    payment_installments,
    cast(payment_value as decimal(14,2))         as payment_value
from {{ source('raw', 'order_payments') }}
