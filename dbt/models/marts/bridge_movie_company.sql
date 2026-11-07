select
    movie_id,
    company_id
from {{ ref('stg_tmdb__movie_companies') }}
