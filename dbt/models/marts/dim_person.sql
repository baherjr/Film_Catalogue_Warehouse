with credits as (

    select person_id, person_name, known_for_department, movie_id
    from {{ ref('stg_tmdb__movie_cast') }}

    union all

    select person_id, person_name, known_for_department, movie_id
    from {{ ref('stg_tmdb__movie_crew') }}

),

ranked as (

    select
        c.person_id,
        c.person_name,
        c.known_for_department,
        -- Latest fetch wins; movie_id breaks ties between films fetched at the same moment.
        -- Ties left after that are one person's several credits on one film (cast plus
        -- crew jobs). They come from the same payload, so they carry the same name and
        -- known_for_department, and whichever row row_number() picks gives the same result.
        row_number() over (
            partition by c.person_id
            order by d.fetched_at desc, c.movie_id desc
        ) as rn
    from credits as c
    join {{ ref('stg_tmdb__movie_details') }} as d
      on d.movie_id = c.movie_id
     and d.is_latest

)

select
    person_id,
    person_name,
    known_for_department
from ranked
where rn = 1
