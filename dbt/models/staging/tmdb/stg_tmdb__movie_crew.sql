select
    c.crew_member ->> 'credit_id' as credit_id,
    d.movie_id,
    (c.crew_member ->> 'id')::bigint as person_id,
    c.crew_member ->> 'name' as person_name,
    c.crew_member ->> 'department' as department,
    c.crew_member ->> 'job' as job
from {{ source('tmdb', 'movie_details') }} as src
join {{ ref('stg_tmdb__movie_details') }} as d
  on d.movie_id = src.movie_id
 and d.payload_sha256 = src.payload_sha256
 and d.is_latest
cross join lateral jsonb_array_elements(src.payload -> 'credits' -> 'crew') as c(crew_member)