-- Every fact row must point at the dim_movie version valid on its snapshot_date:
-- valid_from_date <= snapshot_date < valid_to_date, with a NULL valid_to open.
-- Dates are taken in UTC, the same way fct_movie_popularity_daily does.
select
    f.movie_id,
    f.snapshot_date,
    f.movie_version_key,
    m.valid_from,
    m.valid_to
from {{ ref('fct_movie_popularity_daily') }} as f
join {{ ref('dim_movie') }} as m
  on m.movie_version_key = f.movie_version_key
where f.snapshot_date < (m.valid_from at time zone 'UTC')::date
   or f.snapshot_date >= coalesce((m.valid_to at time zone 'UTC')::date, '9999-12-31'::date)
