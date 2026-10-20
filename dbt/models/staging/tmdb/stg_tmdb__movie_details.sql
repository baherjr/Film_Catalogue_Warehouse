with source as (

    select * from {{ source('tmdb', 'movie_details') }}

),

renamed as (

    select
        -- keys and load metadata: already typed columns
        movie_id,
        payload_sha256,
        fetched_at,

        -- text field: ->> already returns text, no cast needed
        payload ->> 'title' as title,
        payload ->> 'original_title' as original_title,
        payload ->> 'original_language' as original_language,
        payload ->> 'status' as status,
        payload ->> 'imdb_id' as imdb_id,

        -- empty string means unknown: turn '' into NULL before casting
        nullif(payload ->> 'release_date', '')::date as release_date,

        -- 0 means unknown: cast first, then turn 0 into NULL
        nullif((payload ->> 'budget')::bigint, 0) as budget,
        nullif((payload ->> 'revenue')::bigint, 0) as revenue,
        nullif((payload ->> 'runtime')::integer, 0) as runtime,

        -- an average of 0 only happens with 0 votes, so NULL means no votes
        nullif((payload ->> 'vote_average')::numeric, 0) as vote_average,
        -- 0 votes is a real count, not unknown: keep it
        (payload ->> 'vote_count')::integer as vote_count,

        -- newest version per film; payload_sha256 breaks ties so the result is fixed
        row_number() over (
            partition by movie_id
            order by fetched_at desc, payload_sha256 desc
        ) = 1 as is_latest

    from source

)

select * from renamed