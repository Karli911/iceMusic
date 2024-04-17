import sys
import atexit
import asyncio
import threading
from inspect import getmodule
from urllib.request import urlparse
from datetime import datetime, timezone
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context as mp_context
from typing import List, Optional, Union

from aiohttp import ClientResponseError
from yt_dlp import YoutubeDL, DownloadError

from config import config
from musicbot.song import Song
from musicbot.utils import OutputWrapper
from musicbot.linkutils import (
    YT_IE,
    ExtractorT,
    Origins,
    SiteTypes,
    get_ie,
    fetch_spotify,
    identify_url,
    init as init_session,
    stop as stop_session,
)


sys.stdout = OutputWrapper(sys.stdout)
sys.stderr = OutputWrapper(sys.stderr)

_context = mp_context("spawn")


class LoaderProcess(_context.Process):
    def run(self):
        try:
            super().run()
        # suppress noisy errors that happen on Ctrl+C
        except (KeyboardInterrupt, InterruptedError):
            pass


_context.Process = LoaderProcess


async def close_bot_session():
    # close session opened in musicbot/yt_dlp_plugins/extractor/discord.py
    from musicbot.__main__ import bot

    await bot.http.close()


_loop = asyncio.new_event_loop()
_loop.run_until_complete(init_session())
atexit.register(lambda: _loop.run_until_complete(stop_session()))
atexit.register(lambda: _loop.run_until_complete(close_bot_session()))
_executor = ProcessPoolExecutor(1, _context)
_downloader = YoutubeDL(
    {
        "format": "bestaudio/best",
        "extract_flat": True,
        "noplaylist": True,
        # default_search shouldn't be needed as long as
        # we don't pass plain text to the downloader.
        # still leaving it just in case
        "default_search": "auto",
        "cookiefile": config.COOKIE_PATH,
        "quiet": True,
    }
)
_preloading = {}
_site_locks = {}


class SongError(Exception):
    pass


def _noop():
    pass


def init():
    # wake it up to spawn the process immediately
    _executor.submit(_noop).result()


def extract_info(url: str, ie: Optional[ExtractorT] = None) -> Optional[dict]:
    if ie is None:
        ie = get_ie(url)
    # cache by module (effectively means by site)
    # extractor *may* be lazy
    module = getmodule(getattr(ie, "real_class", ie))
    try:
        lock = _site_locks[module]
    except KeyError:
        lock = _site_locks[module] = threading.Lock()
    with lock:
        try:
            return _downloader.extract_info(url, False, ie.ie_key())
        except DownloadError:
            return None


async def search_youtube(title: str, count: int = 1) -> Optional[dict]:
    return await _run_sync(_search_youtube, title, count)


def _search_youtube(title: str, count: int = 1) -> Optional[dict]:
    """Searches youtube for the video title
    Returns the first results video link"""

    r = extract_info(f"ytsearch{count}:{title}")

    if not r:
        return None

    return r["entries"]


async def load_song(track: str) -> Union[Optional[Song], List[Song]]:
    return await _run_sync(_load_song, track)


def _load_song(track: str) -> Union[Optional[Song], List[Song]]:
    host = identify_url(track)

    if host == SiteTypes.NOT_URL:
        data = _search_youtube(track)
        if not data:
            return None
        data = data[0]
        host = SiteTypes.YT_DLP

    elif host == SiteTypes.UNKNOWN:
        return None

    elif host == SiteTypes.SPOTIFY:
        try:
            data = _loop.run_until_complete(fetch_spotify(track))
        except ClientResponseError as e:
            raise SongError(config.SONGINFO_ERROR) from e
        if isinstance(data, list):
            data = [{"url": url} for url in data]

    elif host == SiteTypes.CUSTOM:
        data = {
            "url": track,
            "webpage_url": track,
            "title": urlparse(track).path.rpartition("/")[2],
        }

    else:  # host is info extractor
        data = extract_info(track, host)
        host = SiteTypes.YT_DLP

    if not data:
        raise SongError(config.SONGINFO_ERROR)

    if isinstance(data, dict):
        if "entries" in data:
            # assuming a playlist
            data = data["entries"]
        elif YT_IE.suitable(data["url"]):
            # the URL wasn't extracted, do it now
            data = extract_info(data["url"], YT_IE)
            if not data:
                raise SongError(config.SONGINFO_ERROR)

    if isinstance(data, list):
        results = []
        for entry in data:
            entry.pop("webpage_url", None)
            song = Song(
                Origins.Playlist,
                host,
                webpage_url=entry.pop("url"),
            )
            song.update(entry)
            results.append(song)
        return results

    song = Song(Origins.Default, host, webpage_url=track)
    song.update(data)

    return song


def _parse_expire(url: str) -> Optional[int]:
    expire = (
        ("&" + urlparse(url).query).partition("&expire=")[2].partition("&")[0]
    )
    try:
        return int(expire)
    except ValueError:
        return None


async def preload(song: Song) -> bool:
    if song.webpage_url is None:
        return True

    if song.url is not None:
        expire = _parse_expire(song.url)
        if expire is None or expire == _parse_expire(song.webpage_url):
            return True
        if datetime.now(timezone.utc) < datetime.fromtimestamp(
            expire, timezone.utc
        ):
            return True

    future = _preloading.get(song)
    if future:
        return await future
    _preloading[song] = asyncio.Future()

    try:
        preloaded = await load_song(song.webpage_url)
    except SongError:
        success = False
    else:
        success = preloaded is not None

    if success:
        song.update(preloaded)

    _preloading.pop(song).set_result(success)
    return success


async def _run_sync(f, *args):
    return await asyncio.get_running_loop().run_in_executor(
        _executor, f, *args
    )
