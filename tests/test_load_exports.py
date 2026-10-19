import gzip
import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import psycopg
import pytest

from filmwh.config import DATABASE_URL
from filmwh.load_exports import load_export

TEST_DATE = date(2000, 1, 1)  # never a real export date

ROWS = [
    {
        "adult": False,
        "id": 1,
        "original_title": "Film One",
        "popularity": 1.5,
        "video": False,
    },
    {
        "adult": False,
        "id": 2,
        "original_title": 'Film, Two "quoted"',
        "popularity": 0.2,
        "video": None,
    },
    {
        "adult": True,
        "id": 3,
        "original_title": "Film Three",
        "popularity": 0.0,
        "video": False,
    },
]


@pytest.fixture
def db_conn() -> Iterator[psycopg.Connection]:
    try:
        conn = psycopg.connect(DATABASE_URL)
    except psycopg.OperationalError:
        pytest.skip("Postgres not running")
    yield conn
    conn.execute(
        "DELETE FROM raw.movie_ids_daily WHERE snapshot_date = %s", (TEST_DATE,)
    )
    conn.execute("DELETE FROM raw.export_loads WHERE snapshot_date = %s", (TEST_DATE,))
    conn.commit()
    conn.close()


@pytest.fixture
def export_file(tmp_path: Path) -> Path:
    path = tmp_path / "movie_ids_01_01_2000.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as file:
        for row in ROWS:
            file.write(json.dumps(row) + "\n")
    return path


def count_rows(conn: psycopg.Connection) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM raw.movie_ids_daily WHERE snapshot_date = %s",
            (TEST_DATE,),
        )
        return cursor.fetchone()[0]


def test_export_load_is_idempotent(
    db_conn: psycopg.Connection, export_file: Path
) -> None:
    first = load_export(export_file, TEST_DATE)
    second = load_export(export_file, TEST_DATE)

    assert first == second == len(ROWS)
    assert count_rows(db_conn) == len(ROWS)

    with db_conn.cursor() as cursor:
        cursor.execute(
            "SELECT source_file, row_count FROM raw.export_loads WHERE snapshot_date = %s",
            (TEST_DATE,),
        )
        assert cursor.fetchall() == [(export_file.name, len(ROWS))]
