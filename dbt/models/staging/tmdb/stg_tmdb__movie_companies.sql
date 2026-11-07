-- distinct: TMDB can list the same company twice in one film's payload (1 film on
-- 7 Nov). Without it the film gets two identical rows, which breaks the
-- (movie_id, company_id) uniqueness test and double-counts the film for that company.
select distinct
    d.movie_id,
    (c.company ->> 'id')::bigint as company_id,
    c.company ->> 'name' as company_name,
    nullif(c.company ->> 'origin_country', '') as origin_country
from {{ source('tmdb', 'movie_details') }} as src
join {{ ref('stg_tmdb__movie_details') }} as d
  on d.movie_id = src.movie_id
 and d.payload_sha256 = src.payload_sha256
 and d.is_latest
cross join lateral jsonb_array_elements(src.payload -> 'production_companies') as c(company)