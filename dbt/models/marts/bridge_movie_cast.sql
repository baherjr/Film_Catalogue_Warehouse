select
    credit_id,
    movie_id,
    person_id,
    character_name,
    billing_order
from {{ ref('stg_tmdb__movie_cast') }}
