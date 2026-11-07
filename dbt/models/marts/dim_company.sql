with ranked as (

    select
        c.company_id,
        c.company_name,
        c.origin_country,
        row_number() over (
            partition by c.company_id
            order by d.fetched_at desc, c.movie_id desc
        ) as rn
    from {{ ref('stg_tmdb__movie_companies') }} as c
    join {{ ref('stg_tmdb__movie_details') }} as d
      on d.movie_id = c.movie_id
     and d.is_latest

)

select
    company_id,
    company_name,
    origin_country
from ranked
where rn = 1