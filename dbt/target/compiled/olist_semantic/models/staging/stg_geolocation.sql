select
    geolocation_zip_code_prefix              as zip_code_prefix,
    geolocation_lat                          as latitude,
    geolocation_lng                          as longitude,
    lower(trim(geolocation_city))          as city,
    upper(trim(geolocation_state))           as state
from "olist_dirty"."raw"."geolocation"