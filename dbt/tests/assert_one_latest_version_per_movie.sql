-- every film must have exactly one latest row: count them per film, so zero fails as well as two
select
    movie_id,
    count(*) filter (where is_latest) as latest_rows
from {{ ref('stg_tmdb__movie_details') }}
group by movie_id
having count(*) filter (where is_latest) <> 1
