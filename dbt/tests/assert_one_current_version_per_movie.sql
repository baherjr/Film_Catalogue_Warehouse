-- Each film must have exactly one is_current row in dim_movie.
select
    movie_id,
    count(*) filter (where is_current) as current_versions
from {{ ref('dim_movie') }}
group by movie_id
having count(*) filter (where is_current) <> 1
