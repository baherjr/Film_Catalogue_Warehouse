"""Command line entry point.

`filmwh ingest --limit N`, `filmwh exports --from DATE --to DATE`,
`filmwh refresh [--limit N]` and `filmwh changes --from DATE --to DATE`.
"""

import argparse
import logging
import time
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

from filmwh.exports import ExportNotPublished, download_export, latest_available_export
from filmwh.load_details import changes_details, ingest_details, refresh_details
from filmwh.load_exports import load_export

log = logging.getLogger("filmwh")


def ingest(limit: int) -> None:
    start = time.perf_counter()
    snapshot_date, path = latest_available_export()
    rows = load_export(path, snapshot_date)
    log.info("Loaded %d rows for snapshot date %s", rows, snapshot_date)
    ingest_details(limit)
    end = time.perf_counter()
    log.info("Total time: %.2f seconds", end - start)


def date_range(start: date, end: date) -> Iterator[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def check_date_range(start: date, end: date) -> None:
    if start > end:
        raise ValueError(f"start {start} is after end {end}")
    today = datetime.now(UTC).date()
    if end > today:
        raise ValueError(f"end {end} is after today {today}")


def backfill_exports(start: date, end: date) -> None:
    check_date_range(start, end)

    missing: list[date] = []
    for snapshot_date in date_range(start, end):
        t0 = time.perf_counter()
        try:
            path = download_export(snapshot_date)
        except ExportNotPublished:
            log.warning("Export not published for %s", snapshot_date)
            missing.append(snapshot_date)
            continue
        rows = load_export(path, snapshot_date)
        seconds = time.perf_counter() - t0
        log.info("%s: %d rows in %.1f s", snapshot_date, rows, seconds)

    if missing:
        log.warning("Missing exports: %s", ", ".join(d.isoformat() for d in missing))


def refresh(limit: int | None) -> None:
    start = time.perf_counter()
    refresh_details(limit)
    end = time.perf_counter()
    log.info("Total time: %.2f seconds", end - start)


def changes(start: date, end: date) -> None:
    check_date_range(start, end)
    t0 = time.perf_counter()
    changes_details(start, end)
    log.info("Total time: %.2f seconds", time.perf_counter() - t0)


def main() -> None:
    parser = argparse.ArgumentParser(prog="filmwh")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_parser = sub.add_parser("ingest", help="download, load and fetch details")
    ingest_parser.add_argument(
        "--limit", type=int, default=5000, help="Number of films to fetch details for"
    )

    exports_parser = sub.add_parser(
        "exports", help="download and load daily exports for a date range"
    )
    exports_parser.add_argument(
        "--from", dest="start", type=date.fromisoformat, required=True
    )
    exports_parser.add_argument(
        "--to", dest="end", type=date.fromisoformat, required=True
    )

    refresh_parser = sub.add_parser(
        "refresh", help="refetch details for catalogue films and record changes"
    )
    refresh_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Number of catalogue films to refresh (omit to refresh every catalogue film)",
    )

    changes_parser = sub.add_parser(
        "changes", help="refetch catalogue films TMDB reports as changed"
    )
    changes_parser.add_argument(
        "--from", dest="start", type=date.fromisoformat, required=True
    )
    changes_parser.add_argument(
        "--to", dest="end", type=date.fromisoformat, required=True
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.command == "ingest":
        ingest(args.limit)
    elif args.command == "exports":
        backfill_exports(args.start, args.end)
    elif args.command == "refresh":
        refresh(args.limit)
    elif args.command == "changes":
        changes(args.start, args.end)
