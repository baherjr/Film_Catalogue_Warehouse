# Film Catalogue Warehouse

A local data warehouse built from TMDB movie data: Python ingestion → PostgreSQL → dbt.
Daily popularity snapshots for ~1M films, plus details and credits for the 5,000 most popular.
Stack: Python 3.14, httpx, psycopg, PostgreSQL, dbt, pytest, Docker, GitHub Actions.
Tested with pytest (ingestion) and dbt tests (models, from week 2).

> **Status:** in progress. Week 1 (raw ingestion) is being built now. Sections marked *planned* are not built yet.

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
| Staging | Typed, flattened dbt models | *Planned, week 2* |
| Marts | Popularity snapshot fact; movie, company, person and date dimensions; genre, company and cast bridges; SCD Type 2 on movie attributes | *Planned, weeks 2–3* |

## Design decisions

- **Raw data is stored as JSONB, unchanged.** Flattening happens in dbt staging, so a change in the API's response shape never breaks ingestion, and every model can be rebuilt from raw.
- **Export grain is one row per `(snapshot_date, movie_id)`.** Each day's file is a full snapshot, and this table becomes the periodic snapshot fact.
- **Details are append-only, keyed on `(movie_id, payload_sha256)`.** Re-running ingestion with unchanged data inserts nothing; a changed payload adds a new row. That history feeds the SCD Type 2 snapshot in week 3.
- **Loads are idempotent.** The export loader deletes and reloads a `snapshot_date` inside one transaction, so running it twice gives the same result.
- **API calls are kept low.** Each film costs one request (`append_to_response=credits`); responses are cached on disk; 429 responses are retried with back-off that respects `Retry-After`. Popularity comes from the daily export file, which costs no API calls.
- **Scope is limited.** Development runs on 500 films; the full run covers the 5,000 most popular.
- **One Python version: 3.14.** dbt does not yet support 3.15, so the whole project, including Docker and CI, is pinned to 3.14.

## Run it

Requirements: [uv](https://docs.astral.sh/uv/), Docker, and a TMDB API read access token.

```bash
git clone https://github.com/baherjr/film-catalogue-warehouse.git
cd film-catalogue-warehouse
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

Filled in after the first full run.

| Films | API calls | Wall time | 429 responses |
|---|---|---|---|
| 5,000 | – | – | – |

## Roadmap

- [ ] Week 1: raw ingestion, cached and idempotent, with tests
- [ ] Week 2: dbt staging; star schema designed with the grain of every table documented
- [ ] Week 3: SCD Type 2 via dbt snapshot; incremental loads from TMDB's change feed; model contracts; query tuning with `EXPLAIN ANALYZE`
- [ ] Week 4: Docker Compose (Postgres + ingestion + dbt); GitHub Actions running ruff, pytest and `dbt build`

## Data source and attribution

This product uses the TMDB API but is not endorsed or certified by TMDB.

Data comes from [The Movie Database (TMDB)](https://www.themoviedb.org/) API and its [daily ID exports](https://developer.themoviedb.org/docs/daily-id-exports). This is a personal, non-commercial portfolio project; no TMDB data is redistributed in this repository.