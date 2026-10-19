"""Load a TMDB daily export file into raw.movie_ids_daily."""

import gzip
import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import psycopg

from filmwh.config import DATABASE_URL

COLUMNS = (
    "snapshot_date",
    "movie_id",
    "adult",
    "original_title",
    "popularity",
    "video",
)

type ExportRow = tuple[date, int, bool | None, str | None, float | None, bool | None]


def iter_export_rows(path: Path, snapshot_date: date) -> Iterator[ExportRow]:
    """Yield one tuple per line, in COLUMNS order."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            yield (
                snapshot_date,
                data["id"],
                data["adult"],
                data["original_title"],
                data["popularity"],
                data["video"],
            )


def load_export(path: Path, snapshot_date: date) -> int:
    """Replace one day's rows with the file's contents. Return the row count."""
    with (
        psycopg.connect(DATABASE_URL) as conn,
        conn.transaction(),
        conn.cursor() as cur,
    ):
        cur.execute(
            "DELETE FROM raw.movie_ids_daily WHERE snapshot_date = %s", (snapshot_date,)
        )
        sql = f"COPY raw.movie_ids_daily ({', '.join(COLUMNS)}) FROM STDIN"
        with cur.copy(sql) as copy:
            for row in iter_export_rows(path, snapshot_date):
                copy.write_row(row)
        cur.execute(
            "SELECT COUNT(*) FROM raw.movie_ids_daily WHERE snapshot_date = %s",
            (snapshot_date,),
        )
        row_count = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO raw.export_loads (snapshot_date, source_file, row_count)
            VALUES (%s, %s, %s)
            ON CONFLICT (snapshot_date) DO UPDATE
            SET source_file = EXCLUDED.source_file,
                row_count = EXCLUDED.row_count,
                loaded_at = now()
            """,
            (snapshot_date, path.name, row_count),
        )
    return row_count


if __name__ == "__main__":
    import time

    from filmwh.exports import latest_available_export

    snapshot_date, path = latest_available_export()
    start = time.perf_counter()
    row_count = load_export(path, snapshot_date)
    end = time.perf_counter()

    print(f"Loaded {row_count} rows in {end - start:.2f} seconds.")
