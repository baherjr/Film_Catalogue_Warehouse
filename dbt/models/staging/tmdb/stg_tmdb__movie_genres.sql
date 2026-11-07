-- distinct: TMDB can list the same genre twice in one film's payload (1 film on
-- 7 Nov). Without it the film gets two identical rows, which breaks the
-- (movie_id, genre_id) uniqueness test and double-counts the film in that genre.
select distinct
    d.movie_id,
    (c.genre ->> 'id')::integer as genre_id,
    c.genre ->> 'name' as genre_name
from {{ source('tmdb', 'movie_details') }} as src
join {{ ref('stg_tmdb__movie_details') }} as d
  on d.movie_id = src.movie_id
 and d.payload_sha256 = src.payload_sha256
 and d.is_latest
cross join lateral jsonb_array_elements(src.payload -> 'genres') as c(genre)