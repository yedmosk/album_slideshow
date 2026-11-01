"""Random order: no repeats within a cycle, across cycles, or when the album changes."""
from __future__ import annotations

import random
import types

from custom_components.album_slideshow import camera


def _cam(seed=1):
    cam = camera.AlbumSlideshowCamera.__new__(camera.AlbumSlideshowCamera)
    cam._rng = random.Random(seed)
    cam._index = 0
    cam._random_order = []
    cam._random_pos = 0
    cam._cycle_urls = []
    cam._recent_urls = []
    return cam


def _items(n, prefix="p"):
    return [types.SimpleNamespace(url=f"{prefix}{i}") for i in range(n)]


def _show(cam, items, n):
    shown = []
    for _ in range(n):
        cam._index = cam._next_random_index(len(items), items)
        cam._remember_recent(items[cam._index].url, len(items))
        shown.append(items[cam._index].url)
    return shown


def test_every_photo_once_per_cycle():
    items = _items(60)
    shown = _show(_cam(), items, 60)
    assert sorted(shown) == sorted(it.url for it in items)


def test_photos_shown_last_do_not_come_straight_back():
    for seed in range(20):
        items = _items(60)
        shown = _show(_cam(seed), items, 240)
        last_seen = {}
        for pos, url in enumerate(shown):
            if url in last_seen:
                # Any photo waits at least half the album before repeating.
                assert pos - last_seen[url] > 30, (seed, url, last_seen[url], pos)
            last_seen[url] = pos


def test_small_albums_never_repeat_back_to_back():
    for seed in range(20):
        items = _items(3)
        shown = _show(_cam(seed), items, 30)
        assert all(a != b for a, b in zip(shown, shown[1:]))


def test_album_growing_mid_cycle_keeps_the_cycle():
    cam = _cam()
    items = _items(10)
    first = _show(cam, items, 4)
    grown = items + _items(5, prefix="new")
    rest = _show(cam, grown, 11)
    assert not set(first) & set(rest)
    assert sorted(first + rest) == sorted(it.url for it in grown)


def test_album_shrinking_mid_cycle_keeps_the_cycle():
    cam = _cam()
    items = _items(10)
    first = _show(cam, items, 4)
    # Drop one photo already shown and one not shown yet.
    unseen = next(it.url for it in items if it.url not in first)
    shrunk = [it for it in items if it.url not in (first[0], unseen)]
    rest = _show(cam, shrunk, 5)
    assert not set(first) & set(rest)
    assert set(first[1:] + rest) == {it.url for it in shrunk}


def test_cycle_progress_round_trips_through_the_cursor():
    cam = _cam()
    items = _items(10)
    _show(cam, items, 3)
    cursor = cam._capture_cursor()
    assert cursor.cycle_urls == tuple(cam._cycle_urls)
    assert len(cursor.cycle_urls) == 3
