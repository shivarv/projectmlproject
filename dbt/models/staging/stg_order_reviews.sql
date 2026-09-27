-- raw.order_reviews contains repeated review_id values (a genuine Olist quirk),
-- so this stays at its natural grain and marts aggregate it to one row per order.
select
    review_id,
    order_id,
    review_score,
    review_comment_title,
    review_comment_message,
    review_creation_date                     as review_created_at,
    review_answer_timestamp                  as review_answered_at
from {{ source('raw', 'order_reviews') }}
