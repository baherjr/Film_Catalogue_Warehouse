{{ config(severity='warn') }}

-- People whose name or known_for_department differs across their cast and crew credits.
-- These conflicts come from TMDB (each credit is fetched with a different film), so this
-- warns rather than fails. dim_person keeps the value from the most recently fetched film.
-- About 155 rows on 4 Nov 2026; a sudden jump is the thing to look for.

with credits as (

    select person_id, person_name, known_for_department
    from {{ ref('stg_tmdb__movie_cast') }}

    union all

    select person_id, person_name, known_for_department
    from {{ ref('stg_tmdb__movie_crew') }}

)

select
    person_id,
    count(distinct person_name)          as name_count,
    count(distinct known_for_department) as department_count
from credits
group by person_id
having count(distinct person_name) > 1
    or count(distinct known_for_department) > 1
