-- Single-version form: every film has exactly one version, backdated to the
-- start of the export (section 4). Change detection on status, runtime, budget
-- and revenue arrives in week 6, once films have real second versions.

with details as (

    select
        movie_id,
        '2026-08-01 00:00:00+00'::timestamptz as valid_from,
        status,
        runtime,
        budget,
        revenue,
        title,
        original_title,
        original_language,
        imdb_id,
        release_date,
        vote_count,
        vote_average,
        fetched_at as details_fetched_at
    from {{ ref('stg_tmdb__movie_details') }}
    where is_latest

),

-- The export view sits on ~120M rows: restrict to catalogue films first,
-- then keep each film's latest snapshot.
export_flags as (

    select distinct on (e.movie_id)
        e.movie_id,
        e.is_adult,
        e.is_video
    from {{ ref('stg_tmdb__movie_ids_daily') }} as e
    join details as d
      on d.movie_id = e.movie_id
    order by e.movie_id, e.snapshot_date desc

)

select
    {{ dbt_utils.generate_surrogate_key(['d.movie_id', 'd.valid_from']) }} as movie_version_key,
    d.movie_id,

    -- Type 2
    d.status,
    d.runtime,
    d.budget,
    d.revenue,

    -- Type 1
    d.title,
    d.original_title,
    d.original_language,
    d.imdb_id,
    d.release_date,
    f.is_adult,
    f.is_video,
    d.vote_count,
    d.vote_average,
    d.details_fetched_at,

    -- validity
    d.valid_from,
    null::timestamptz as valid_to,
    true as is_current
from details as d
left join export_flags as f
  on f.movie_id = d.movie_id
