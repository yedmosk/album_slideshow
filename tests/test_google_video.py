"""Google Photos video slides: stream fallback in the proxy."""
from __future__ import annotations

import asyncio
import types

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestClient, TestServer

from custom_components.album_slideshow import video
from custom_components.album_slideshow.const import DOMAIN
from custom_components.album_slideshow.coordinator import MediaItem

_CLIP = bytes(range(256)) * 40


def test_upstream_urls_fall_back_for_google_streams_only():
    assert video.upstream_urls("https://lh3.googleusercontent.com/pw/x=m22") == [
        "https://lh3.googleusercontent.com/pw/x=m22",
        "https://lh3.googleusercontent.com/pw/x=m18",
        "https://lh3.googleusercontent.com/pw/x=dv",
    ]
    assert video.upstream_urls("http://immich/api/assets/a/video/playback") == [
        "http://immich/api/assets/a/video/playback"
    ]


def _run_proxy(monkeypatch, available, scenario):
    """Serve the view against an upstream that only has the ``available`` variants."""
    hits = []

    async def stream(request):
        variant = request.match_info["variant"]
        hits.append(variant)
        if variant not in available:
            return web.Response(status=404)
        return web.Response(body=_CLIP, content_type="video/mp4")

    async def main():
        upstream_app = web.Application()
        upstream_app.router.add_get("/pw/clip={variant}", stream)
        async with TestServer(upstream_app) as upstream:
            item = MediaItem(
                url="poster", width=None, height=None, mime_type=None, filename=None,
                source_id="vid", video_url=str(upstream.make_url("/pw/clip=m22")),
            )
            coord = types.SimpleNamespace(data={"items": [item]}, image_request_headers={})
            hass = types.SimpleNamespace(data={DOMAIN: {"entry": {"coordinator": coord}}})
            view = video.AlbumSlideshowVideoView(hass)
            async with ClientSession() as session:
                monkeypatch.setattr(video, "async_get_clientsession", lambda *_a, **_kw: session)

                async def handler(request):
                    return await view.get(request, **request.match_info)

                app = web.Application()
                app.router.add_get("/video/{entry_id}/{photo_id}", handler)
                async with TestClient(TestServer(app)) as client:
                    return await scenario(client, item.photo_id), hits

    return asyncio.run(main())


async def _fetch(client, photo_id):
    resp = await client.get(f"/video/entry/{photo_id}")
    return resp.status, await resp.read()


def test_proxy_serves_the_720p_stream_when_google_has_it(monkeypatch):
    (status, body), hits = _run_proxy(monkeypatch, {"m22", "m18", "dv"}, _fetch)
    assert (status, body) == (200, _CLIP)
    assert hits == ["m22"]


def test_proxy_falls_back_to_360p_then_the_original(monkeypatch):
    (status, body), hits = _run_proxy(monkeypatch, {"dv"}, _fetch)
    assert (status, body) == (200, _CLIP)
    assert hits == ["m22", "m18", "dv"]


def test_proxy_gives_up_when_no_variant_exists(monkeypatch):
    (status, _), hits = _run_proxy(monkeypatch, set(), _fetch)
    assert status == 502
    assert hits == ["m22", "m18", "dv"]
