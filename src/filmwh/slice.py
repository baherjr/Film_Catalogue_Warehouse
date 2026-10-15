"""Pick which films get detail fetches: the most popular in the latest snapshot."""

import psycopg

from filmwh.config import DATABASE_URL

TOP_MOVIES_SQL = """
    SELECT movie_id
    FROM raw.movie_ids_daily
    WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM raw.movie_ids_daily)
      AND adult IS NOT TRUE 
    ORDER BY popularity DESC NULLS LAST, movie_id
    LIMIT %s
"""


def top_n_movie_ids(limit: int) -> list[int]:
    """Return the IDs of the `limit` most popular non-adult films."""
    if limit < 1:
        raise ValueError("Limit must be at least 1")
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(TOP_MOVIES_SQL, (limit,))
            return [row[0] for row in cur.fetchall()]


if __name__ == "__main__":
    first = top_n_movie_ids(500)
    second = top_n_movie_ids(500)
    print(f"{len(first)} IDs, first 10: {first[:10]}")
    print("Same order on both runs:", first == second)