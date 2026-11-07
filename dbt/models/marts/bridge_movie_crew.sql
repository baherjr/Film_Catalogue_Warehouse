select
    credit_id,
    movie_id,
    person_id,
    department,
    job
from {{ ref('stg_tmdb__movie_crew') }}
