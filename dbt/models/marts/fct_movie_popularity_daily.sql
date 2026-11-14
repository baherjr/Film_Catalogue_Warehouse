-- Periodic snapshot: one row per catalogue film per day it appears in the
-- daily export (docs/star_schema.md, section 2).

-- Rank over the whole export (~120M rows), before any filter: a rank of 40
-- means 40th of every film TMDB lists that day, not 40th of the catalogue.
with ranked as (

    select
        snapshot_date,
        movie_id,
        popularity,
        rank() over (
            partition by snapshot_date
            order by popularity desc nulls last
        ) as popularity_rank
    from {{ ref('stg_tmdb__movie_ids_daily') }}

),

-- is_latest is already one row per film (assert_one_latest_version_per_movie),
-- so no distinct is needed.
catalogue as (

    select movie_id
    from {{ ref('stg_tmdb__movie_details') }}
    where is_latest

),

scoped as (

    select r.*
    from ranked as r
    join catalogue as c
      on c.movie_id = r.movie_id

),

-- Day boundaries in UTC, explicitly. A bare timestamptz::date uses the
-- session's TimeZone, so a different connection setting would silently move
-- a version's first day.
versions as (

    select
        movie_version_key,
        movie_id,
        (valid_from at time zone 'UTC')::date as valid_from_date,
        coalesce((valid_to at time zone 'UTC')::date, '9999-12-31'::date) as valid_to_date
    from {{ ref('dim_movie') }}

)

-- Point-in-time join: the version valid on snapshot_date. valid_to is
-- exclusive, so a day belongs to exactly one version. An inner join drops a
-- row whose date matches no version; B3c checks that count(scoped) equals the
-- fact's row count.
select
    v.movie_version_key,
    s.movie_id,
    s.snapshot_date,
    s.popularity,
    s.popularity_rank
from scoped as s
join versions as v
  on v.movie_id = s.movie_id
 and s.snapshot_date >= v.valid_from_date
 and s.snapshot_date < v.valid_to_date