"""Command line entry point: `filmwh ingest --limit N`."""

import argparse
import logging
import time

from filmwh.exports import latest_available_export
from filmwh.load_details import ingest_details
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


def main() -> None:
    parser = argparse.ArgumentParser(prog="filmwh")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_parser = sub.add_parser("ingest", help="download, load and fetch details")
    ingest_parser.add_argument(
        "--limit", type=int, default=500, help="Number of movies to process"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.command == "ingest":
        ingest(args.limit)
