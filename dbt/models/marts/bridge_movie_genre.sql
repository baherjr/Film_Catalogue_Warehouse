select
    movie_id,
    genre_id
from {{ ref('stg_tmdb__movie_genres') }}
