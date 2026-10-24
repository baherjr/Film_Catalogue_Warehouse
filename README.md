# Film Catalogue Warehouse

A local data warehouse built from TMDB movie data: Python ingestion → PostgreSQL → dbt.
Daily popularity snapshots for ~1.26M films, daily since 1 August 2026, plus details and credits for every film that has been in the top 5,000 by popularity on a day ingestion ran: 6,829 films as of 24 October 2026, and growing as new films enter the top 5,000.
Stack: Python 3.14, httpx, psycopg, PostgreSQL, dbt, pytest, Docker, GitHub Actions.
Tested with pytest (ingestion) and dbt tests (models, from week 2).

> **Status:** in progress. Weeks 1–2 complete: raw ingestion and dbt staging. Sections marked *planned* are not built yet.

---

## What it answers

1. Which genres and studios keep their popularity after release?
2. How do budget and revenue relate, by genre and by decade?

## Architecture

```
TMDB daily export (.json.gz) ──► raw.movie_ids_daily      ┐
                                                           ├──► dbt staging ──► star schema (planned)
TMDB API: details + credits ──► raw.movie_details (JSONB) ┘
```

| Layer | Contents | Status |
|---|---|---|
| Raw | Daily export rows and full API payloads, as received | Week 1 |
| Staging | Typed, flattened dbt models | Week 2 |
| Marts | Popularity snapshot fact; movie, company, person and date dimensions; genre, company and cast bridges; SCD Type 2 on movie attributes | *Planned, weeks 3–4* |

## Design decisions

- **Raw data is stored as JSONB, unchanged.** Flattening happens in dbt staging, so a change in the API's response shape never breaks ingestion, and every model can be rebuilt from raw.
- **Export grain is one row per `(snapshot_date, movie_id)`.** Each day's file is a full snapshot, and this table becomes the periodic snapshot fact.
- **Details are append-only, keyed on `(movie_id, payload_sha256)`.** Re-running ingestion with unchanged data inserts nothing; a changed payload would add a new row. In practice no history builds up yet: a cached film is never fetched again, so each film's details are a one-time snapshot from the day it was first fetched. Refetching changed films from TMDB's change feed will create new versions, and the SCD Type 2 snapshot (week 4) depends on that.
- **Staging keeps every details version.** `stg_tmdb__movie_details` exposes all payload versions of a film, with `is_latest` marking the most recent, so the SCD Type 2 model can read the full history once refetching produces one. Today every film has exactly one version.
- **Credits come from the latest version only.** Cast and crew are unnested from each film's latest payload, so every credit appears once per film and counts of films per actor or director aren't inflated. Those counts cover only the films in the details slice, not a person's whole career.
- **Loads are idempotent.** The export loader deletes and reloads a `snapshot_date` inside one transaction, so running it twice gives the same result.
- **API calls are kept low.** Each film costs one request (`append_to_response=credits`); responses are cached on disk; 429 responses are retried with back-off that respects `Retry-After`. Popularity comes from the daily export file, which costs no API calls.
- **Scope is limited.** Each run fetches details for the 5,000 most popular films in that day's export (`--limit`, default 5,000). Films that drop out of the top 5,000 keep their stored details, so the slice only grows.
- **One Python version: 3.14.** dbt does not yet support 3.15, so the whole project, including Docker and CI, is pinned to 3.14.

## Run it

Requirements: [uv](https://docs.astral.sh/uv/), Docker, and a TMDB API read access token.

```bash
git clone https://github.com/baherjr/Film_Catalogue_Warehouse.git
cd Film_Catalogue_Warehouse
cp .env.example .env            # add TMDB_API_TOKEN and Postgres settings
docker compose up -d postgres
uv sync
uv run filmwh ingest --limit 5000
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

## dbt build (week 2)

`dbt build` on 24 October 2026: 4 staging models, 20 data tests, all passing in about 4 s. The data covers 85 daily exports (1 August to 24 October 2026) and 6,829 films with details. Reloading a day's export and rebuilding changes no counts (checked on 22 October 2026).

| Model | Grain | Rows |
|---|---|---|
| `stg_tmdb__movie_ids_daily` | film × snapshot date | 105,748,079 |
| `stg_tmdb__movie_details` | film × payload version | 6,829 |
| `stg_tmdb__movie_cast` | cast credit, latest version | 273,616 |
| `stg_tmdb__movie_crew` | crew credit, latest version | 630,715 |

These counts grow with every daily run.

## Known issues

- **Film details are frozen at first fetch.** The disk cache never expires and nothing refetches a film, so a film keeps the details it had on the day it entered the slice. A film first fetched on 15 October 2026 shows that day's vote count, status, budget and revenue indefinitely. Anyone querying the movie dimension (`dim_movie`) needs to read these attributes as of each film's `fetched_at`, not as current values. Change-feed refetching will fix this, and SCD Type 2 depends on it.
- **Detail fetching is sequential.** Requests run one at a time at about 6 per second, well under TMDB's limit of roughly 40 per second, and the full run hit no 429s. Fetching with a small pool of concurrent requests should cut the 12-minute fetch substantially. Planned for the week 5 performance lab.
- **Detail inserts send every payload, one row at a time.** Each row is sent in full and checked against `ON CONFLICT`, even when it's unchanged, so an all-cached rerun still spends about 3 minutes in the insert step. The fix is to read the existing `(movie_id, payload_sha256)` pairs first and batch only new rows. Planned for week 3 query tuning.

## Roadmap

- [x] Week 1: raw ingestion, cached and idempotent, with tests
- [x] Week 2: dbt staging for exports, details, cast and crew; 20 tests, including a deliberate failure check
- [ ] Week 3: star schema with the grain of every table documented; incremental loads from TMDB's change feed; model contracts; query tuning with `EXPLAIN ANALYZE`
- [ ] Week 4: SCD Type 2 via dbt snapshot; Docker Compose (Postgres + ingestion + dbt); GitHub Actions running ruff, pytest and `dbt build`

## Data source and attribution

This product uses the TMDB API but is not endorsed or certified by TMDB.

Data comes from [The Movie Database (TMDB)](https://www.themoviedb.org/) API and its [daily ID exports](https://developer.themoviedb.org/docs/daily-id-exports). This is a personal, non-commercial portfolio project; no TMDB data is redistributed in this repository.