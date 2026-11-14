# Film Catalogue Warehouse

A local data warehouse built from TMDB movie data: Python ingestion → PostgreSQL → dbt.
Daily popularity snapshots for ~1.26M films since 1 August 2026, plus details and credits for the most popular films (8,264 as of 14 November 2026).
Stack: Python 3.14, httpx, psycopg, PostgreSQL, dbt, pytest, Docker. GitHub Actions CI is planned.
Tested with pytest (ingestion) and dbt tests (models).

> **Status:** in progress. Built: raw ingestion (daily exports, details and credits, refetching from TMDB's change feed), dbt staging, and the star schema: the daily popularity fact, the movie dimension with SCD Type 2, the company, person, genre and date dimensions, and the genre, company, cast and crew bridges.

---

## What it answers

1. Which genres and studios keep their popularity after release?
2. How do budget and revenue relate, by genre and by decade?

## Architecture

```
TMDB daily export (.json.gz) ──► raw.movie_ids_daily      ┐
                                                           ├──► dbt staging ──► star schema
TMDB API: details + credits ──► raw.movie_details (JSONB) ┘
```

| Layer | Contents | Status |
|---|---|---|
| Raw | Daily export rows and full API payloads, as received | Built |
| Staging | Typed, flattened dbt models | Built |
| Marts | Popularity snapshot fact; movie, company, person, genre and date dimensions; genre, company, cast and crew bridges; SCD Type 2 on movie attributes | Built |

## Design decisions

- **Raw data is stored as JSONB, unchanged.** Flattening happens in dbt staging, so a change in the API's response shape never breaks ingestion, and every model can be rebuilt from raw.
- **Export grain is one row per `(snapshot_date, movie_id)`.** Each day's file is a full snapshot, and this table becomes the periodic snapshot fact.
- **Details are append-only, keyed on `(movie_id, payload_sha256)`.** Re-running ingestion with unchanged data inserts nothing; a changed payload adds a new row. `filmwh refresh` refetches every catalogue film, and `filmwh changes` refetches only the films TMDB's change feed lists, so history builds up in raw and `dim_movie` turns it into SCD Type 2 versions.
- **Staging keeps every details version.** `stg_tmdb__movie_details` exposes all payload versions of a film, with `is_latest` marking the most recent, so `dim_movie` can read the full history. On 14 November 2026, 199 of 8,264 films had a second version.
- **Credits come from the latest version only.** Cast and crew are unnested from each film's latest payload, so every credit appears once per film and counts of films per actor or director aren't inflated. Those counts cover only the films in the details slice, not a person's whole career.
- **Loads are idempotent.** The export loader deletes and reloads a `snapshot_date` inside one transaction, so running it twice gives the same result.
- **API calls are kept low.** Each film costs one request (`append_to_response=credits`); responses are cached on disk; 429 responses are retried with back-off that respects `Retry-After`. Popularity comes from the daily export file, which costs no API calls.
- **Scope is limited.** Each run fetches details for the 5,000 most popular films in that day's export (`--limit`, default 5,000). Films that drop out of the top 5,000 keep their stored details, so the slice only grows: it holds every film that has been in the top 5,000 on a day ingestion ran.
- **One Python version: 3.14.** dbt does not yet support 3.15, so the whole project, including Docker and CI, is pinned to 3.14.

## Run it

Requirements: [uv](https://docs.astral.sh/uv/), Docker, and a TMDB API read access token.

```bash
git clone https://github.com/baherjr/Film_Catalogue_Warehouse.git
cd Film_Catalogue_Warehouse
cp .env.example .env            # add TMDB_API_TOKEN and Postgres settings
docker compose up -d postgres
uv sync
uv run filmwh ingest --limit 5000                        # load today's export, fetch details for the top 5,000
uv run filmwh exports --from 2026-08-01 --to 2026-08-31  # backfill daily exports
uv run filmwh refresh [--limit N]                        # refetch every catalogue film (or the first N)
uv run filmwh changes --from 2026-11-13 --to 2026-11-14  # refetch the films TMDB's change feed lists
```

## Tests

```bash
uv run pytest
```

| Test | Checks |
|---|---|
| Cache hit | A cached film makes no HTTP request |
| Rate limit | A 429 response is retried and then succeeds |
| Idempotent load | Loading the same export twice gives the same row count |
| Change-feed paging | Every page of `/movie/changes` is read and the ids collected |
| No changes | A day with no changes makes one call |
| Page limit | More than 500 pages fails on page 1 |
| 14-day limit | A window over 14 days is rejected before any request |
| Day windows | The day windows cover the range with no gaps or overlaps |

## Run metrics

First full run, on 15 October 2026's export, Windows 11 + Docker Desktop, Python 3.14.
Command: `uv run filmwh ingest --limit 5000`

| Metric | Value |
|---|---|
| Export rows loaded | 1,258,757 |
| Export load time | ~9 s (`COPY`) |
| Films in slice | 5,000 (0 not found) |
| API calls | ~4,500 (the rest were already cached) |
| 429 responses | 0 |
| Detail fetch time | ~12 min (~6 requests/s, sequential) |
| Detail insert time | ~3 min 15 s |
| **Total wall time** | **15 min 35 s** |

A second run with everything cached makes no API calls and inserts no rows.

## dbt build

### Staging (as of 24 October 2026)

`dbt build` on 24 October 2026: 4 staging models, 20 data tests, all passing in about 4 s. The data covers 85 daily exports (1 August to 24 October 2026) and 6,829 films with details. Reloading a day's export and rebuilding changes no counts (checked on 22 October 2026).

| Model | Grain | Rows |
|---|---|---|
| `stg_tmdb__movie_ids_daily` | film × snapshot date | 105,748,079 |
| `stg_tmdb__movie_details` | film × payload version | 6,829 |
| `stg_tmdb__movie_cast` | cast credit, latest version | 273,616 |
| `stg_tmdb__movie_crew` | crew credit, latest version | 630,715 |

These counts grow with every daily run.

### Marts

Row counts from `dbt build` on 14 November 2026: 106 daily exports (1 August to 14 November) and 8,264 films with details.

| Model | Grain | Rows |
|---|---|---|
| `fct_movie_popularity_daily` | film × snapshot date | 860,269 |
| `dim_movie` | film version (SCD Type 2) | 8,463 |
| `dim_person` | person | 405,293 |
| `dim_company` | production company | 9,088 |
| `dim_genre` | genre | 19 |
| `dim_date` | calendar day | 58,804 |
| `bridge_movie_crew` | crew credit | 692,912 |
| `bridge_movie_cast` | cast credit | 315,164 |
| `bridge_movie_company` | film × company | 26,860 |
| `bridge_movie_genre` | film × genre | 20,919 |

## Known issues

- **Versions are dated by when a change was fetched, not when TMDB made it.** Running `filmwh changes` daily keeps that within a day. Changes made before the first refresh on 14 November 2026 are all dated 14 November, so each film's first version covers everything back to 1 August.
- **Deleted films stay current.** A film TMDB has removed (e.g. 1503825) returns no payload on refetch, so its last version never closes. Planned for week 7.
- **Detail fetching is sequential.** Requests run one at a time at about 6 per second, well under TMDB's limit of roughly 40 per second, and the full run hit no 429s. Fetching with a small pool of concurrent requests should cut the 12-minute fetch substantially. Planned for week 7.
- **Detail inserts send every payload, one row at a time.** Each row is sent in full and checked against `ON CONFLICT`, even when it's unchanged, so an all-cached rerun still spends about 3 minutes in the insert step. The fix is to read the existing `(movie_id, payload_sha256)` pairs first and batch only new rows. Planned for week 7.

## Roadmap

- [x] Raw ingestion, cached and idempotent
- [x] dbt staging with tests
- [x] Star schema: popularity fact, five dimensions, four bridges
- [x] SCD Type 2 from payload history; refresh and change-feed refetching
- [ ] Incremental fact with late-arriving backfill; deleted films; `EXPLAIN ANALYZE` and indexes; batched inserts
- [ ] dbt contracts and source freshness; Docker Compose for the whole stack; GitHub Actions CI

## Data source and attribution

This product uses the TMDB API but is not endorsed or certified by TMDB.

Data comes from [The Movie Database (TMDB)](https://www.themoviedb.org/) API and its [daily ID exports](https://developer.themoviedb.org/docs/daily-id-exports). This is a personal, non-commercial portfolio project; no TMDB data is redistributed in this repository.