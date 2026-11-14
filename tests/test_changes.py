from datetime import date
from pathlib import Path

import httpx
import pytest

from filmwh.load_details import change_windows
from filmwh.tmdb_client import ChangesWindowTooLarge, TmdbClient


def make_client(handler, tmp_path: Path) -> TmdbClient:
    http = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.themoviedb.org/3",
    )
    return TmdbClient(token="unused", cache_dir=tmp_path, http=http)


def test_changed_ids_collects_every_page(tmp_path: Path) -> None:
    pages = {
        "1": {"results": [{"id": 1}, {"id": 2}], "total_pages": 2},
        "2": {"results": [{"id": 2}, {"id": 3}], "total_pages": 2},
    }
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params["page"]
        seen.append(page)
        return httpx.Response(200, json=pages[page])

    client = make_client(handler, tmp_path)
    ids = client.changed_movie_ids(date(2026, 11, 13), date(2026, 11, 13))
    client.close()

    assert ids == {1, 2, 3}
    assert seen == ["1", "2"]


def test_changed_ids_with_no_changes_makes_one_call(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"results": [], "total_pages": 0})

    client = make_client(handler, tmp_path)
    assert client.changed_movie_ids(date(2026, 11, 13), date(2026, 11, 13)) == set()
    client.close()
    assert len(calls) == 1


def test_too_many_pages_fails_on_first_page(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"results": [{"id": 1}], "total_pages": 501})

    client = make_client(handler, tmp_path)
    with pytest.raises(ChangesWindowTooLarge):
        client.changed_movie_ids(date(2026, 11, 1), date(2026, 11, 14))
    client.close()
    assert len(calls) == 1


def test_window_over_14_days_is_rejected(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail(f"Unexpected HTTP request to {request.url}")

    client = make_client(handler, tmp_path)
    with pytest.raises(ValueError):
        client.changed_movie_ids(date(2026, 11, 1), date(2026, 11, 16))
    client.close()


def test_change_windows_are_single_days_covering_the_range() -> None:
    windows = list(change_windows(date(2026, 11, 12), date(2026, 11, 14)))
    assert windows == [
        (date(2026, 11, 12), date(2026, 11, 12)),
        (date(2026, 11, 13), date(2026, 11, 13)),
        (date(2026, 11, 14), date(2026, 11, 14)),
    ]
