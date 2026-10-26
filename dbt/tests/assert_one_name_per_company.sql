select
    c.company_id,
    count(distinct  c.company_name) as company_name_count
from {{ ref('stg_tmdb__movie_companies') }} as c
group by c.company_id
having count(distinct c.company_name) > 1