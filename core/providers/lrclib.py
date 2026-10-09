"""
core/providers/lrclib.py — LRCLIB 备用歌词提供源
"""
from __future__ import annotations

from typing import Optional

import requests

from .base import BaseLyricProvider, RawLyricResult, SearchSongItem

TIMEOUT = 5

LRCLIB_HEADERS = {
    "User-Agent": "LyrikFlow/1.0 (https://github.com/lyrikflow)",
}


class LrclibLyricProvider(BaseLyricProvider):
    provider_name = "lrclib"

    def search_song(self, title: str, artist: str) -> Optional[SearchSongItem]:
        url = "https://lrclib.net/api/search"
        params = {"q": f"{title} {artist}".strip()}
        try:
            resp = requests.get(url, params=params, headers=LRCLIB_HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                items = resp.json()
                if isinstance(items, list) and items:
                    item = items[0]
                    return SearchSongItem(
                        song_id=str(item.get("id")),
                        title=item.get("trackName", title),
                        artist=item.get("artistName", artist),
                        album=item.get("albumName", ""),
                        duration_ms=int(item.get("duration", 0)) * 1000,
                        provider=self.provider_name,
                    )
        except Exception:
            pass
        return None

    def search_songs(self, title: str, artist: str = "", limit: int = 15) -> list[SearchSongItem]:
        url = "https://lrclib.net/api/search"
        params = {"q": f"{title} {artist}".strip()}
        results: list[SearchSongItem] = []
        try:
            resp = requests.get(url, params=params, headers=LRCLIB_HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                items = resp.json()
                if isinstance(items, list):
                    for item in items[:limit]:
                        results.append(SearchSongItem(
                            song_id=str(item.get("id")),
                            title=item.get("trackName", title),
                            artist=item.get("artistName", artist),
                            album=item.get("albumName", ""),
                            duration_ms=int(item.get("duration", 0)) * 1000,
                            provider=self.provider_name,
                        ))
        except Exception:
            pass
        return results

    def get_lyrics(self, song_item: SearchSongItem) -> Optional[RawLyricResult]:
        url = f"https://lrclib.net/api/get/{song_item.song_id}"
        try:
            resp = requests.get(url, headers=LRCLIB_HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                lrc = data.get("syncedLyrics") or data.get("plainLyrics") or ""
                is_inst = bool(data.get("instrumental"))
                if lrc or is_inst:
                    return RawLyricResult(
                        provider=self.provider_name,
                        song_id=song_item.song_id,
                        title=song_item.title,
                        artist=song_item.artist,
                        lrc=lrc.strip(),
                        is_instrumental=is_inst,
                    )
        except Exception:
            pass
        return None
