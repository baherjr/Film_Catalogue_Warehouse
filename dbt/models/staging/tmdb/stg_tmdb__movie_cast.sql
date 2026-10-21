select
    c.cast_member ->> 'credit_id' as credit_id,
    d.movie_id,
    (c.cast_member ->> 'id')::bigint as person_id,
    c.cast_member ->> 'name' as person_name,
    c.cast_member ->> 'character' as character_name,
    (c.cast_member ->> 'order')::integer as billing_order,
    c.cast_member ->> 'known_for_department' as known_for_department
from {{ source('tmdb', 'movie_details') }} as src
join {{ ref('stg_tmdb__movie_details') }} as d
  on d.movie_id = src.movie_id
 and d.payload_sha256 = src.payload_sha256
 and d.is_latest
cross join lateral jsonb_array_elements(src.payload -> 'credits' -> 'cast') as c(cast_member)