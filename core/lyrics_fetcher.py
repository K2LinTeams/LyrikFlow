"""
lyrics_fetcher.py — 歌词获取模块
支持：
  1. 网易云音乐 eapi 接口（获取官方 yrc 逐字歌词 + tlyric 翻译 + lrc）
  2. 网易云普通 api（保底）
  3. LRCLIB 公开 API（备用源）
"""
from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

EAPI_KEY = b"e82ckenh8dichen8"
TIMEOUT = 8

NETEASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://music.163.com/",
}

EAPI_HEADERS = {
    "User-Agent": "NeteaseMusic/3.0.18.203152",
    "Referer": "https://music.163.com/",
    "Cookie": "os=pc; osver=Microsoft-Windows-10-Professional-build-19045-64bit; appver=3.0.18.203152;",
}

LRCLIB_HEADERS = {
    "User-Agent": "LyrikFlow/1.0 (https://github.com/lyrikflow)",
}

try:
    from core import db_cache
except ImportError:
    import db_cache

# 内存缓存：(title, artist) -> bundle
_cache: dict[str, Optional[dict]] = {}


def eapi_encrypt(url: str, data: dict) -> str:
    text = json.dumps(data)
    message = f"nobody{url}use{text}md5forencrypt"
    digest = hashlib.md5(message.encode("utf-8")).hexdigest()
    data_str = f"{url}-36cd479b6b5-{text}-36cd479b6b5-{digest}"
    cipher = AES.new(EAPI_KEY, AES.MODE_ECB)
    return cipher.encrypt(pad(data_str.encode("utf-8"), AES.block_size)).hex().upper()


def get_lyrics_bundle(title: str, artist: str) -> Optional[dict]:
    """
    返回歌词字典:
    {
        "yrc": str (逐字歌词内容，如有),
        "lrc": str (标准 LRC 歌词),
        "tlyric": str (翻译 LRC 歌词，如有),
        "hd_cover": bytes|None (原画专辑封面),
        "song_id": str (网易云音乐歌曲 ID),
        "sub_name": str (歌曲副名称/别名/翻译名称)
    }
    """
    cache_key = f"{title.lower().strip()}|||{artist.lower().strip()}"
    if cache_key in _cache:
        return _cache[cache_key]

    # 1. 优先从 SQLite 本地持久化缓存快速读取 (0ms)
    cached_db = db_cache.get_song_cache(title, artist)
    if cached_db and (cached_db.get("yrc") or cached_db.get("lrc")):
        _cache[cache_key] = cached_db
        return cached_db

    # 2. 本地无缓存，从网络拉取
    bundle = _fetch_netease(title, artist)
    if not bundle:
        bundle = _fetch_lrclib(title, artist)

    if bundle:
        # 写入 SQLite 持久化缓存
        db_cache.save_song_cache(
            title=title,
            artist=artist,
            yrc=bundle.get("yrc", ""),
            lrc=bundle.get("lrc", ""),
            tlyric=bundle.get("tlyric", ""),
            hd_cover=bundle.get("hd_cover"),
            song_id=str(bundle.get("song_id", "")),
            sub_name=bundle.get("sub_name", ""),
        )

    _cache[cache_key] = bundle
    return bundle


def get_lyrics(title: str, artist: str) -> Optional[str]:
    """向后兼容接口：优先返回 yrc，若无则返回 lrc"""
    bundle = get_lyrics_bundle(title, artist)
    if not bundle:
        return None
    return bundle.get("yrc") or bundle.get("lrc")


def _fetch_netease(title: str, artist: str) -> Optional[dict]:
    song_id = _netease_search(title, artist)
    if not song_id:
        return None

    sub_name, pic_url = _fetch_netease_detail_info(song_id)
    hd_cover = _download_hd_cover(pic_url) if pic_url else None
    yrc, lrc, tlyric = _fetch_netease_lyrics_text(song_id)

    if yrc or lrc:
        return {
            "yrc": yrc,
            "lrc": lrc,
            "tlyric": tlyric,
            "hd_cover": hd_cover,
            "song_id": str(song_id),
            "sub_name": sub_name,
        }

    return None


def _fetch_netease_detail_info(song_id: int) -> tuple[str, Optional[str]]:
    """任务点 1: 获取副歌名与原画专辑封面 URL"""
    sub_name = ""
    pic_url = None

    try:
        url = f"https://music.163.com/api/song/detail?ids=[{song_id}]"
        resp = requests.get(url, headers=NETEASE_HEADERS, timeout=4)
        if resp.status_code == 200:
            songs = resp.json().get("songs", [])
            if songs:
                s = songs[0]
                tns = s.get("transNames") or s.get("tns")
                alia = s.get("alias") or s.get("alia")
                if tns and isinstance(tns, list) and len(tns) > 0 and tns[0]:
                    sub_name = str(tns[0]).strip()
                elif alia and isinstance(alia, list) and len(alia) > 0 and alia[0]:
                    sub_name = str(alia[0]).strip()
                pic_url = s.get("album", {}).get("picUrl") or s.get("al", {}).get("picUrl")
    except Exception:
        pass

    return sub_name, pic_url


def _download_hd_cover(pic_url: str) -> Optional[bytes]:
    """任务点 2: 下载原画 300x300 专辑封面"""
    if not pic_url:
        return None
    try:
        hd_url = f"{pic_url}?param=300y300"
        resp = requests.get(hd_url, headers=NETEASE_HEADERS, timeout=4)
        if resp.status_code == 200 and len(resp.content) > 1000:
            return resp.content
    except Exception:
        pass
    return None


def _fetch_netease_lyrics_text(song_id: int) -> tuple[str, str, str]:
    """任务点 3: 获取歌词文本 (yrc, lrc, tlyric)"""
    # 1. 优先调用 eapi 接口获取 yrc 逐字歌词
    try:
        url = "/api/song/lyric/v1"
        api_url = "https://interface3.music.163.com/eapi/song/lyric/v1"
        data = {
            "id": str(song_id),
            "lv": -1,
            "tv": -1,
            "yv": -1,
            "kv": -1,
            "rv": -1,
        }
        params = {"params": eapi_encrypt(url, data)}
        resp = requests.post(api_url, data=params, headers=EAPI_HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            res_json = resp.json()
            yrc = res_json.get("yrc", {}).get("lyric", "")
            lrc = res_json.get("lrc", {}).get("lyric", "")
            tlyric = res_json.get("tlyric", {}).get("lyric", "")
            if yrc or lrc:
                return (yrc.strip() if yrc else "", lrc.strip() if lrc else "", tlyric.strip() if tlyric else "")
    except Exception:
        pass

    # 2. 回退普通接口
    try:
        url = "https://music.163.com/api/song/lyric"
        params = {"id": song_id, "lv": -1, "tv": -1}
        resp = requests.get(url, params=params, headers=NETEASE_HEADERS, timeout=TIMEOUT)
        data = resp.json()
        lrc = data.get("lrc", {}).get("lyric", "")
        tlyric = data.get("tlyric", {}).get("lyric", "")
        if lrc:
            return ("", lrc.strip(), tlyric.strip() if tlyric else "")
    except Exception:
        pass

    return ("", "", "")


def _fetch_netease_song_detail(song_id: int) -> tuple[Optional[bytes], str]:
    """向后兼容接口：获取封面与副歌名"""
    sub_name, pic_url = _fetch_netease_detail_info(song_id)
    hd_cover = _download_hd_cover(pic_url) if pic_url else None
    return hd_cover, sub_name


def _netease_search(title: str, artist: str) -> Optional[int]:
    t = title.strip()
    if t.isdigit() and len(t) >= 4:
        try:
            # 优先验证是否为直接传入的网易云歌曲 ID
            url = f"https://music.163.com/api/song/detail?ids=[{t}]"
            resp = requests.get(url, headers=NETEASE_HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                songs = resp.json().get("songs", [])
                if songs and str(songs[0].get("id")) == t:
                    return int(t)
        except Exception:
            pass

    keyword = f"{title} {artist}".strip()
    url = "https://music.163.com/api/search/get"
    payload = {"s": keyword, "type": 1, "limit": 5, "offset": 0}
    try:
        resp = requests.post(url, data=payload, headers=NETEASE_HEADERS, timeout=TIMEOUT)
        songs = resp.json().get("result", {}).get("songs", [])
        if not songs:
            return None
        title_lower = title.lower()
        for song in songs:
            if song.get("name", "").lower() == title_lower:
                return song["id"]
        return songs[0]["id"]
    except Exception:
        return None


def _fetch_lrclib(title: str, artist: str) -> Optional[dict]:
    url = "https://lrclib.net/api/get"
    params = {"track_name": title, "artist_name": artist}
    try:
        resp = requests.get(url, params=params, headers=LRCLIB_HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            lrc = data.get("syncedLyrics") or data.get("plainLyrics")
            if lrc:
                return {"yrc": "", "lrc": lrc.strip(), "tlyric": "", "sub_name": ""}
    except Exception:
        pass
    return None


# ── 导出分步任务点接口 ───────────────────────────────────────────────────
netease_search = _netease_search
fetch_netease_detail_info = _fetch_netease_detail_info
download_hd_cover = _download_hd_cover
fetch_netease_lyrics_text = _fetch_netease_lyrics_text
fetch_lrclib = _fetch_lrclib
