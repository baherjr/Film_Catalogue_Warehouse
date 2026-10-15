"""TMDB API client: movie details + credits, cached on disk."""

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from datetime import datetime, timezone

import httpx

from filmwh.config import API_BASE_URL, CACHE_DIR, HTTP_TIMEOUT_SECONDS, TMDB_API_TOKEN

log = logging.getLogger("httpx").setLevel(logging.WARNING)


RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 5
MAX_DELAY_SECONDS = 60  # ceiling on Retry-After, so a bad header can't stall the run


class MovieNotFound(Exception):
    """TMDB has no details for this movie ID (404)."""


class TmdbClient:
    def __init__(
        self,
        token: str = TMDB_API_TOKEN,
        cache_dir: Path = CACHE_DIR,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cache_dir = cache_dir
        self.sleep = sleep  # tests pass a fake so they don't actually wait
        # Tests pass their own client here, which is why it's a parameter.
        if http is None:
            self.http = httpx.Client(
                base_url=API_BASE_URL,
                timeout=HTTP_TIMEOUT_SECONDS,
                headers={"Authorization": f"Bearer {token}"},
            )
        else:
            self.http = http

    def _get(self, url: str, params: dict) -> httpx.Response:
        """GET with retries. Returns the final response; raises if attempts run out."""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self.http.get(url, params=params)
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt == MAX_ATTEMPTS:
                    raise
                delay = 2 ** (attempt - 1)
                log.warning(
                    "GET %s failed (%s), retrying in %ss (attempt %d of %d)",
                    url, exc, delay, attempt, MAX_ATTEMPTS,
                )
                self.sleep(delay)
                continue

            if response.status_code not in RETRY_STATUSES:
                return response  # success, or an error retrying won't fix

            if attempt == MAX_ATTEMPTS:
                return response

            retry_after = response.headers.get("Retry-After", "")
            delay = int(retry_after) if retry_after.isdigit() else 2 ** (attempt - 1)
            if delay > MAX_DELAY_SECONDS:
                log.warning(
                    "GET %s asked for Retry-After %ss, capping at %ss",
                    url, delay, MAX_DELAY_SECONDS,
                )
                delay = MAX_DELAY_SECONDS
            log.warning(
                "GET %s returned %d, retrying in %ss (attempt %d of %d)",
                url, response.status_code, delay, attempt, MAX_ATTEMPTS,
            )
            self.sleep(delay)
        raise AssertionError("unreachable")

    def _cache_path(self, movie_id: int) -> Path:
        return self.cache_dir / f"{movie_id}.json"

    def get_movie(self, movie_id: int, refresh: bool = False) -> dict:
        """Return the details+credits payload for one film.

        Reads from the cache unless refresh=True.
        """
        path = self._cache_path(movie_id)
        if not refresh and path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        response = self._get(f"/movie/{movie_id}", params={"append_to_response": "credits"})
        if response.status_code == 404:
            raise MovieNotFound(f"Movie {movie_id} not found")
        response.raise_for_status()

        # Write to a .part file, then replace into place
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        part_path = path.with_suffix(".part")
        with open(part_path, "w", encoding="utf-8") as f:
            f.write(response.text)
        part_path.replace(path)

        return response.json()

    def fetched_at(self, movie_id: int) -> datetime:
        """When this film's cached payload was fetched (cache file write time, UTC)."""
        path = self._cache_path(movie_id)
        if not path.exists():
            raise FileNotFoundError(f"Cache file for movie {movie_id} does not exist")
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

    def close(self) -> None:
        self.http.close()




if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    client = TmdbClient()
    try:
        movie = client.get_movie(550)
        print(movie["title"], "| cast:", len(movie["credits"]["cast"]))
        movie = client.get_movie(550)  # second call: from cache
        print("second call OK")
    finally:
        client.close()