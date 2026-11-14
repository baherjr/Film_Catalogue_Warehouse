-- Each version of a film must end exactly where the next one starts, and must
-- not end before it starts. dim_movie's design makes overlaps impossible today;
-- this test protects it from a future edit.
with ordered as (

    select
        movie_id,
        movie_version_key,
        valid_from,
        valid_to,
        lead(valid_from) over (
            partition by movie_id order by valid_from
        ) as next_valid_from
    from {{ ref('dim_movie') }}

)

select *
from ordered
where valid_to <= valid_from
   or valid_to is distinct from next_valid_from
