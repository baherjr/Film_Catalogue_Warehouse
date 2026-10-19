SELECT
    snapshot_date,
    movie_id,
    adult AS is_adult,
    original_title,
    popularity,
    video AS is_video
FROM
    {{ source('tmdb', 'movie_ids_daily') }}
