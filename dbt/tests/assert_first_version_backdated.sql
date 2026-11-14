-- Every film's first version must be backdated to the start of the export.
select
    movie_id,
    min(valid_from) as first_valid_from
from {{ ref('dim_movie') }}
group by movie_id
having min(valid_from) <> '2026-08-01 00:00:00+00'::timestamptz
