import json
from pathlib import Path

import httpx
import pytest

from filmwh.tmdb_client import TmdbClient

FIXTURE = Path(__file__).parent / "fixtures" / "movie_550.json"


def failing_handler(request: httpx.Request) -> httpx.Response:
    pytest.fail(f"Unexpected HTTP request to {request.url}")


def test_cache_hit_makes_no_http_call(tmp_path: Path) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    (tmp_path / "550.json").write_text(json.dumps(payload), encoding="utf-8")
    with httpx.Client(
        transport=httpx.MockTransport(failing_handler),
        base_url="https://api.themoviedb.org/3",
    ) as http:
        client = TmdbClient(token="unused", cache_dir=tmp_path, http=http)
        assert client.get_movie(550) == payload
        client.close()