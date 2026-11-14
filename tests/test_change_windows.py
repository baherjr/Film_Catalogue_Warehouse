from datetime import date, timedelta
from itertools import pairwise

from filmwh.load_details import CHANGES_WINDOW_DAYS, change_windows
from filmwh.tmdb_client import MAX_CHANGES_WINDOW

ONE_DAY = timedelta(days=1)


def test_single_day() -> None:
    day = date(2026, 11, 14)
    assert change_windows(day, day) == [(day, day)]


def test_windows_tile_the_range_without_gaps_or_overlap() -> None:
    start, end = date(2026, 10, 1), date(2026, 11, 14)
    windows = change_windows(start, end)
    assert windows[0][0] == start
    assert windows[-1][1] == end
    for (_, prev_end), (next_start, _) in pairwise(windows):
        assert next_start == prev_end + ONE_DAY
    # Inclusive length of each window: at most CHANGES_WINDOW_DAYS days...
    assert all(
        (e - s) + ONE_DAY <= timedelta(days=CHANGES_WINDOW_DAYS) for s, e in windows
    )
    # ...and always a span the changes endpoint accepts.
    assert all(e - s <= MAX_CHANGES_WINDOW for s, e in windows)
