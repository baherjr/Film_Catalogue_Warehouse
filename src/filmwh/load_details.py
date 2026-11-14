"""Fetch details+credits and land them in raw.movie_details.

Three entry points: ingest_details fetches today's top-N slice (cached films
are read from disk), refresh_details refetches every catalogue film, and
changes_details refetches the catalogue films TMDB's change feed lists.
"""

import hashlib
import json
import logging
from datetime import date, datetime, timedelta
from itertools import batched
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from filmwh.config import DATABASE_URL
from filmwh.slice import top_n_movie_ids
from filmwh.tmdb_client import MovieNotFound, TmdbClient

log = logging.getLogger(__name__)

INSERT_SQL = """
    INSERT INTO raw.movie_details (movie_id, payload_sha256, payload, fetched_at)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (movie_id, payload_sha256) DO NOTHING
"""

CATALOGUE_IDS_SQL = """
    SELECT DISTINCT movie_id
    FROM raw.movie_details
    ORDER BY movie_id
    LIMIT %s
"""

REFRESH_BATCH_SIZE = 500

# One day per /movie/changes query: a 14-day window holds more than the 500
# pages TMDB will serve, so it can't be read in full.
CHANGES_WINDOW_DAYS = 1

type DetailRow = tuple[int, str, Jsonb, datetime]


def payload_sha256(payload: dict[str, Any]) -> str:
    # Frozen format: changing any option here changes every stored hash, and the
    # next run would insert a fake "new version" of every film.
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def collect_rows(
    client: TmdbClient, movie_ids: list[int], refresh: bool = False
) -> tuple[list[DetailRow], int]:
    """Fetch every film; return (rows to insert, number of films not found)."""
    rows: list[DetailRow] = []
    not_found = 0
    for i, movie_id in enumerate(movie_ids, start=1):
        try:
            payload = client.get_movie(movie_id, refresh=refresh)
        except MovieNotFound:
            not_found += 1
            log.warning("Movie %d not found", movie_id)
            continue

        rows.append(
            (
                movie_id,
                payload_sha256(payload),
                Jsonb(payload),
                client.fetched_at(movie_id),
            )
        )

        # Counts within this call: per batch under refresh_details, which also
        # logs overall progress after each batch.
        if i % 100 == 0:
            log.info("fetched %d of %d", i, len(movie_ids))

    return rows, not_found


def insert_rows(rows: list[DetailRow]) -> int:
    """Insert in one transaction; return how many rows were actually new."""
    inserted = 0
    with (
        psycopg.connect(DATABASE_URL) as conn,
        conn.transaction(),
        conn.cursor() as cur,
    ):
        for row in rows:
            cur.execute(INSERT_SQL, row)
            inserted += cur.rowcount
    return inserted


def ingest_details(limit: int) -> None:
    client = TmdbClient()
    try:
        movie_ids = top_n_movie_ids(limit)
        rows, not_found = collect_rows(client, movie_ids)
        log.info("inserting %d rows", len(rows))
        inserted = insert_rows(rows)
    finally:
        client.close()
    log.info(
        "films: %d | not found: %d | new rows: %d | unchanged: %d",
        len(movie_ids),
        not_found,
        inserted,
        len(rows) - inserted,
    )


def catalogue_movie_ids(limit: int | None = None) -> list[int]:
    """Return the IDs of films already in raw.movie_details (all if limit is None)."""
    if limit is not None and limit < 1:
        raise ValueError("Limit must be at least 1")
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        # LIMIT NULL means no limit in Postgres.
        cur.execute(CATALOGUE_IDS_SQL, (limit,))
        movie_ids = [row[0] for row in cur.fetchall()]
    log.info("catalogue has %d movie IDs", len(movie_ids))
    return movie_ids


def refetch(client: TmdbClient, movie_ids: list[int]) -> None:
    """Refetch films from TMDB in batches; each batch commits on its own."""
    films = not_found = fetched = inserted = 0
    for batch in batched(movie_ids, REFRESH_BATCH_SIZE):
        rows, batch_not_found = collect_rows(client, list(batch), refresh=True)
        batch_inserted = insert_rows(rows)
        films += len(batch)
        not_found += batch_not_found
        fetched += len(rows)
        inserted += batch_inserted
        log.info(
            "batch done: %d of %d films | new rows: %d (total %d)",
            films,
            len(movie_ids),
            batch_inserted,
            inserted,
        )
    log.info(
        "films: %d | not found: %d | new rows: %d | unchanged: %d",
        films,
        not_found,
        inserted,
        fetched - inserted,
    )


def refresh_details(limit: int | None = None) -> None:
    """Refetch every catalogue film; insert a row wherever the payload changed."""
    client = TmdbClient()
    try:
        refetch(client, catalogue_movie_ids(limit))
    finally:
        client.close()


def change_windows(start: date, end: date) -> list[tuple[date, date]]:
    """Split start..end (inclusive) into windows of CHANGES_WINDOW_DAYS days."""
    step = timedelta(days=CHANGES_WINDOW_DAYS)
    windows: list[tuple[date, date]] = []
    window_start = start
    while window_start <= end:
        window_end = min(window_start + step - timedelta(days=1), end)
        windows.append((window_start, window_end))
        window_start = window_end + timedelta(days=1)
    return windows


def changes_details(start: date, end: date) -> None:
    """Refetch the catalogue films TMDB lists as changed from start to end."""
    client = TmdbClient()
    try:
        changed: set[int] = set()
        for window_start, window_end in change_windows(start, end):
            window_ids = client.changed_movie_ids(window_start, window_end)
            log.info(
                "changes %s to %s: %d ids", window_start, window_end, len(window_ids)
            )
            changed |= window_ids
        catalogue = set(catalogue_movie_ids())
        movie_ids = sorted(changed & catalogue)
        log.info(
            "changed ids seen: %d | in catalogue: %d", len(changed), len(movie_ids)
        )
        refetch(client, movie_ids)
    finally:
        client.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    ingest_details(500)