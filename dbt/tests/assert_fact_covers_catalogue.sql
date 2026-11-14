-- Every catalogue film (one is_latest row each) must have rows in the fact.
with counts as (

    select
        (select count(distinct movie_id)
         from {{ ref('fct_movie_popularity_daily') }}) as fact_films,
        (select count(*)
         from {{ ref('stg_tmdb__movie_details') }}
         where is_latest) as catalogue_films

)

select *
from counts
where fact_films <> catalogue_films
