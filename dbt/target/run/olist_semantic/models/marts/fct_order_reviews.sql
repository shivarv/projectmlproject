
    

    create  table
      "olist_dirty"."marts"."fct_order_reviews__dbt_tmp"
  
    
    as (
      -- One row per order. raw.order_reviews can carry several reviews per order
-- and repeated review_ids, so aggregating here prevents a join fan-out.
select
    order_id,
    count(*)                    as review_count,
    min(review_score)           as review_score,
    round(avg(review_score), 2) as avg_review_score,
    max(review_created_at)      as last_review_at
from "olist_dirty"."staging"."stg_order_reviews"
group by 1
    );
    
  