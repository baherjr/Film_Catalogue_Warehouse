select
    genre_id,
    genre_name
from {{ ref('tmdb_genres') }}
