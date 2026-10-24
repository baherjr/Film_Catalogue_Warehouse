"""Fetch details+credits for the slice and land them in raw.movie_details."""

import hashlib
import json
import logging
from datetime import datetime
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

type DetailRow = tuple[int, str, Jsonb, datetime]


def payload_sha256(payload: dict[str, Any]) -> str:
    # Frozen format: changing any option here changes every stored hash, and the
    # next run would insert a fake "new version" of every film.
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def collect_rows(
    client: TmdbClient, movie_ids: list[int]
) -> tuple[list[DetailRow], int]:
    """Fetch every film; return (rows to insert, number of films not found)."""
    rows: list[DetailRow] = []
    not_found = 0
    for i, movie_id in enumerate(movie_ids, start=1):
        try:
            payload = client.get_movie(movie_id)
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


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    ingest_details(500)
