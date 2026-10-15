"""Download TMDB's daily movie ID export files."""

import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from filmwh.config import EXPORT_BASE_URL, EXPORT_DIR, HTTP_TIMEOUT_SECONDS

log = logging.getLogger(__name__)


class ExportNotPublished(Exception):
    """TMDB hasn't published the export for the requested date yet."""


def export_filename(snapshot_date: date) -> str:
    return f"movie_ids_{snapshot_date.strftime('%m_%d_%Y')}.json.gz"


def export_url(snapshot_date: date) -> str:
    return EXPORT_BASE_URL + export_filename(snapshot_date)


def download_export(snapshot_date: date, dest_dir: Path = EXPORT_DIR) -> Path:
    """Download one day's export to dest_dir and return its path.

    Skips the download if the file is already on disk.
    """
    final_path = dest_dir / export_filename(snapshot_date)
    if final_path.exists():
        log.info("%s already on disk", final_path.name)
        return final_path

    dest_dir.mkdir(parents=True, exist_ok=True)

    part_path = final_path.with_suffix(final_path.suffix + ".part")

    url = export_url(snapshot_date)
    with httpx.stream("GET", url, timeout=HTTP_TIMEOUT_SECONDS) as response:
        if response.status_code in (403, 404):
            raise ExportNotPublished(
                f"{url} is not published yet ({response.status_code})"
            )
        if response.status_code != 200:
            raise RuntimeError(f"Failed to download {url}: {response.status_code}")
        with open(part_path, "wb") as f:
            f.writelines(response.iter_bytes())

    part_path.replace(final_path)
    return final_path


def latest_available_export(dest_dir: Path = EXPORT_DIR) -> tuple[date, Path]:
    """Return today's export (UTC), or yesterday's if today's isn't published yet."""
    today_utc = datetime.now(UTC).date()
    for snapshot_date in (today_utc, today_utc - timedelta(days=1)):
        try:
            path = download_export(snapshot_date, dest_dir)
            return snapshot_date, path
        except ExportNotPublished:
            log.info("No export for %s yet, trying the previous day", snapshot_date)
    raise RuntimeError("No export found for today or yesterday")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    snapshot_date, path = latest_available_export()
    size_mb = path.stat().st_size / 1_000_000
    print(f"{snapshot_date}: {path} ({size_mb:.2f} MB)")
