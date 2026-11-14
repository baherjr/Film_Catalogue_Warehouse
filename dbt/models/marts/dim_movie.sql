-- Type 2 on status, runtime, budget and revenue. A film gets a new version
-- whenever one of those differs from its previous payload; the other columns
-- are Type 1, taken from the latest payload. The first version of every film
-- is backdated to the start of the export (section 4).

-- Every payload, not just the latest: change detection needs the history.
with payloads as (

    select
        movie_id,
        fetched_at,
        payload_sha256,
        status,
        runtime,
        budget,
        revenue
    from {{ ref('stg_tmdb__movie_details') }}

),

-- Compare each payload with the one before it, not with distinct values:
-- A -> B -> A has to give three versions, not two.
flagged as (

    select
        *,
        row_number() over w = 1 as is_first_payload,
        row_number() over w = 1
            or status is distinct from lag(status) over w
            or runtime is distinct from lag(runtime) over w
            or budget is distinct from lag(budget) over w
            or revenue is distinct from lag(revenue) over w
            as starts_version
    from payloads
    -- payload_sha256 breaks ties, the same way is_latest does
    window w as (partition by movie_id order by fetched_at, payload_sha256)

),

versions as (

    select
        movie_id,
        case
            when is_first_payload then '2026-08-01 00:00:00+00'::timestamptz
            else fetched_at
        end as valid_from,
        status,
        runtime,
        budget,
        revenue
    from flagged
    where starts_version

),

-- lead() runs only after the filter above. Over all payloads, every version
-- would end at the next refetch, even when that refetch changed nothing.
validity as (

    select
        *,
        lead(valid_from) over (partition by movie_id order by valid_from) as valid_to
    from versions

),

latest as (

    select
        movie_id,
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
    join latest as l
      on l.movie_id = e.movie_id
    order by e.movie_id, e.snapshot_date desc

)

select
    {{ dbt_utils.generate_surrogate_key(['v.movie_id', 'v.valid_from']) }} as movie_version_key,
    v.movie_id,

    -- Type 2
    v.status,
    v.runtime,
    v.budget,
    v.revenue,

    -- Type 1
    l.title,
    l.original_title,
    l.original_language,
    l.imdb_id,
    l.release_date,
    f.is_adult,
    f.is_video,
    l.vote_count,
    l.vote_average,
    l.details_fetched_at,

    -- validity
    v.valid_from,
    v.valid_to,
    v.valid_to is null as is_current
from validity as v
join latest as l
  on l.movie_id = v.movie_id
left join export_flags as f
  on f.movie_id = v.movie_id
