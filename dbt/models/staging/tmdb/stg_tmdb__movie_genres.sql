select
    d.movie_id,
    (c.genre ->> 'id')::integer as genre_id,
    c.genre ->> 'name' as genre_name
from {{ source('tmdb', 'movie_details') }} as src
join {{ ref('stg_tmdb__movie_details') }} as d
  on d.movie_id = src.movie_id
 and d.payload_sha256 = src.payload_sha256
 and d.is_latest
cross join lateral jsonb_array_elements(src.payload -> 'genres') as c(genre)