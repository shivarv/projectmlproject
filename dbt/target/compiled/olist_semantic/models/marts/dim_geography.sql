-- Resolves the 152x fan-out: raw.geolocation holds 1,000,163 points across
-- only 19,015 zips (up to 1,146 rows for a single zip). Collapsed to exactly
-- one row per zip so a join can never multiply orders.
select
    zip_code_prefix,
    round(median(latitude), 6)   as latitude,
    round(median(longitude), 6)  as longitude,
    mode(city)                   as city,
    mode(state)                  as state,
    count(*)                     as source_point_count
from "olist_dirty"."staging"."stg_geolocation"
group by 1