CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.movie_ids_daily (
    snapshot_date   DATE             NOT NULL,
    movie_id        BIGINT           NOT NULL,
    -- Nullable: the raw layer keeps TMDB's values as sent, and TMDB sends some nulls.
    adult           BOOLEAN,
    original_title  TEXT,
    popularity      DOUBLE PRECISION,
    video           BOOLEAN,
    source_file     TEXT             NOT NULL,
    loaded_at       TIMESTAMPTZ      NOT NULL DEFAULT now(),
    CONSTRAINT pk_movie_ids_daily PRIMARY KEY (snapshot_date, movie_id)
);

COMMENT ON TABLE raw.movie_ids_daily IS
    'Grain: one row per movie per day it appears in TMDB''s daily movie ID export. Reloaded per snapshot_date.';

CREATE TABLE IF NOT EXISTS raw.movie_details (
    movie_id        BIGINT      NOT NULL,
    payload_sha256  TEXT        NOT NULL
        CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    payload         JSONB       NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL,
    loaded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_movie_details PRIMARY KEY (movie_id, payload_sha256)
);

CREATE INDEX IF NOT EXISTS ix_movie_details_latest
    ON raw.movie_details (movie_id, fetched_at DESC);

COMMENT ON TABLE raw.movie_details IS
    'Grain: one row per distinct version of a film''s TMDB details+credits payload. Append-only.';