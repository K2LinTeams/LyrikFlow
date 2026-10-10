"""
core/providers/netease.py — 网易云音乐 API 提供源
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from .base import BaseLyricProvider, RawLyricResult, SearchSongItem

EAPI_KEY = b"e82ckenh8dichen8"
TIMEOUT = 6

NETEASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Referer": "https://music.163.com/",
    "Cookie": "os=pc; osver=Microsoft-Windows-11-Professional-build-22631-64bit; appver=3.1.34.205264;",
}


def eapi_encrypt(url: str, data: dict) -> str:
    """网易云 EAPI AES-128-ECB 请求体加密与签名"""
    text = json.dumps(data)
    message = f"nobody{url}use{text}md5forencrypt"
    digest = hashlib.md5(message.encode("utf-8")).hexdigest()
    data_str = f"{url}-36cd479b6b5-{text}-36cd479b6b5-{digest}"
    cipher = AES.new(EAPI_KEY, AES.MODE_ECB)
    return cipher.encrypt(pad(data_str.encode("utf-8"), 16)).hex().upper()


class NeteaseLyricProvider(BaseLyricProvider):
    provider_name = "netease"

    def search_song(self, title: str, artist: str) -> Optional[SearchSongItem]:
        t = title.strip()
        # 若传入纯数字 ID 则优先直查详情
        if t.isdigit() and len(t) >= 4:
            item = self._get_song_by_id(t)
            if item:
                return item

        keyword = f"{title} {artist}".strip()
        url_path = "/api/cloudsearch/pc"
        api_url = "https://interface.music.163.com/eapi/cloudsearch/pc"
        payload = {
            "s": keyword,
            "type": "1",
            "limit": "10",
            "offset": "0",
            "total": "true",
        }

        try:
            params = {"params": eapi_encrypt(url_path, payload)}
            resp = requests.post(api_url, data=params, headers=NETEASE_HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                songs = resp.json().get("result", {}).get("songs", [])
                if songs:
                    return self._pick_best_song(songs, title, artist)
        except Exception:
            pass

        # 回退 Web 搜索
        return self._search_web_fallback(keyword, title, artist)

    def _parse_song_item(self, best: dict) -> SearchSongItem:
        s_id = str(best.get("id", ""))
        s_name = best.get("name", "")
        ar_list = [a.get("name", "") for a in (best.get("ar") or best.get("artists") or []) if a.get("name")]
        s_artist = "/".join(ar_list)
        album_obj = best.get("al") or best.get("album") or {}
        s_album = album_obj.get("name", "")
        pic_url = album_obj.get("picUrl")

        # 提取副标题/别名
        sub_name = ""
        tns = best.get("tns") or best.get("transNames")
        alia = best.get("alia") or best.get("alias")
        if tns and isinstance(tns, list) and tns[0]:
            sub_name = str(tns[0]).strip()
        elif isinstance(tns, str) and tns.strip():
            sub_name = tns.strip()
        elif best.get("transName"):
            sub_name = str(best["transName"]).strip()
        elif alia and isinstance(alia, list) and alia[0]:
            sub_name = str(alia[0]).strip()
        elif isinstance(alia, str) and alia.strip():
            sub_name = alia.strip()

        return SearchSongItem(
            song_id=s_id,
            title=s_name,
            artist=s_artist,
            album=s_album,
            duration_ms=int(best.get("dt") or best.get("duration") or 0),
            pic_url=pic_url,
            sub_name=sub_name,
            provider=self.provider_name,
        )

    def _pick_best_song(self, songs: list[dict], title: str, artist: str) -> SearchSongItem:
        title_lower = title.lower().strip()
        artist_lower = artist.lower().strip()

        best = songs[0]
        # 寻找完全同名且歌手匹配的歌曲
        for s in songs:
            s_name = (s.get("name") or "").lower().strip()
            s_artists = [a.get("name", "").lower().strip() for a in (s.get("ar") or s.get("artists") or [])]
            if s_name == title_lower:
                if any(artist_lower in a or a in artist_lower for a in s_artists if a):
                    best = s
                    break

        return self._parse_song_item(best)

    def search_songs(self, title: str, artist: str = "", limit: int = 15) -> list[SearchSongItem]:
        keyword = f"{title} {artist}".strip()
        url_path = "/api/cloudsearch/pc"
        api_url = "https://interface.music.163.com/eapi/cloudsearch/pc"
        payload = {
            "s": keyword,
            "type": "1",
            "limit": str(limit),
            "offset": "0",
            "total": "true",
        }
        results: list[SearchSongItem] = []
        try:
            params = {"params": eapi_encrypt(url_path, payload)}
            resp = requests.post(api_url, data=params, headers=NETEASE_HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                songs = resp.json().get("result", {}).get("songs", [])
                for s in songs:
                    item = self._parse_song_item(s)
                    if item.song_id:
                        results.append(item)
        except Exception:
            pass

        if not results:
            single = self.search_song(title, artist)
            if single:
                results.append(single)
        return results

    def _get_song_by_id(self, song_id: str) -> Optional[SearchSongItem]:
        try:
            url = f"https://music.163.com/api/song/detail?ids=[{song_id}]"
            resp = requests.get(url, headers=NETEASE_HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                songs = resp.json().get("songs", [])
                if songs and str(songs[0].get("id")) == song_id:
                    s = songs[0]
                    ar_list = [a.get("name", "") for a in s.get("artists", []) if a.get("name")]
                    pic_url = s.get("album", {}).get("picUrl")
                    sub_name = ""
                    tns = s.get("transNames") or s.get("tns")
                    alia = s.get("alias") or s.get("alia")
                    if tns and isinstance(tns, list) and tns[0]:
                        sub_name = str(tns[0]).strip()
                    elif isinstance(tns, str) and tns.strip():
                        sub_name = tns.strip()
                    elif s.get("transName"):
                        sub_name = str(s["transName"]).strip()
                    elif alia and isinstance(alia, list) and alia[0]:
                        sub_name = str(alia[0]).strip()
                    elif isinstance(alia, str) and alia.strip():
                        sub_name = alia.strip()

                    return SearchSongItem(
                        song_id=song_id,
                        title=s.get("name", ""),
                        artist="/".join(ar_list),
                        album=s.get("album", {}).get("name", ""),
                        pic_url=pic_url,
                        sub_name=sub_name,
                        provider=self.provider_name,
                    )
        except Exception:
            pass
        return None

    def _search_web_fallback(self, keyword: str, title: str, artist: str) -> Optional[SearchSongItem]:
        try:
            url = "https://music.163.com/api/search/get"
            payload = {"s": keyword, "type": 1, "limit": 5, "offset": 0}
            resp = requests.post(url, data=payload, headers=NETEASE_HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                songs = resp.json().get("result", {}).get("songs", [])
                if songs:
                    return self._pick_best_song(songs, title, artist)
        except Exception:
            pass
        return None

    def get_lyrics(self, song_item: SearchSongItem) -> Optional[RawLyricResult]:
        song_id = song_item.song_id
        # 1. 优先调用 EAPI /song/lyric/v1
        try:
            url_path = "/api/song/lyric/v1"
            api_url = "https://interface3.music.163.com/eapi/song/lyric/v1"
            payload = {
                "id": str(song_id),
                "cp": "false",
                "lv": "0",
                "kv": "0",
                "tv": "0",
                "rv": "0",
                "yv": "0",
                "ytv": "0",
                "yrv": "0",
            }
            params = {"params": eapi_encrypt(url_path, payload)}
            resp = requests.post(api_url, data=params, headers=NETEASE_HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                rj = resp.json()
                is_pure_music = bool(rj.get("nolyric") or rj.get("pureMusic"))
                yrc = (rj.get("yrc", {}).get("lyric") or "").strip()
                lrc = (rj.get("lrc", {}).get("lyric") or "").strip()
                tlyric = (rj.get("tlyric", {}).get("lyric") or "").strip()
                romalrc = (rj.get("romalrc", {}).get("lyric") or "").strip()

                if yrc or lrc or is_pure_music:
                    return RawLyricResult(
                        provider=self.provider_name,
                        song_id=song_id,
                        title=song_item.title,
                        artist=song_item.artist,
                        sub_name=song_item.sub_name,
                        yrc=yrc,
                        lrc=lrc,
                        tlyric=tlyric,
                        romalrc=romalrc,
                        pic_url=song_item.pic_url,
                        is_instrumental=is_pure_music,
                    )
        except Exception:
            pass

        # 2. 回退普通接口
        try:
            url = "https://music.163.com/api/song/lyric"
            params = {"id": song_id, "lv": -1, "tv": -1, "rv": -1}
            resp = requests.get(url, params=params, headers=NETEASE_HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                rj = resp.json()
                lrc = (rj.get("lrc", {}).get("lyric") or "").strip()
                tlyric = (rj.get("tlyric", {}).get("lyric") or "").strip()
                romalrc = (rj.get("romalrc", {}).get("lyric") or "").strip()
                if lrc or rj.get("nolyric"):
                    return RawLyricResult(
                        provider=self.provider_name,
                        song_id=song_id,
                        title=song_item.title,
                        artist=song_item.artist,
                        sub_name=song_item.sub_name,
                        lrc=lrc,
                        tlyric=tlyric,
                        romalrc=romalrc,
                        pic_url=song_item.pic_url,
                        is_instrumental=bool(rj.get("nolyric")),
                    )
        except Exception:
            pass

        return None

    def download_cover(self, pic_url: str) -> Optional[bytes]:
        if not pic_url:
            return None
        try:
            hd_url = f"{pic_url}?param=500y500" if "?" not in pic_url else pic_url
            resp = requests.get(hd_url, headers=NETEASE_HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200 and len(resp.content) > 1000:
                return resp.content
        except Exception:
            pass
        return None
