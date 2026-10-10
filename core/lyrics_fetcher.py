"""
core/lyrics_fetcher.py — 多源歌词获取
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from core import db_cache, settings
from core.lyrics_parser import ParsedLyrics, parse_raw_bundle
from core.providers import (
    LrclibLyricProvider,
    NeteaseLyricProvider,
    QQMusicLyricProvider,
    RawLyricResult,
    SearchSongItem,
)

# 音源单例
NETEASE_PROVIDER = NeteaseLyricProvider()
QQMUSIC_PROVIDER = QQMusicLyricProvider()
LRCLIB_PROVIDER = LrclibLyricProvider()

# 内存 LRU 快速缓存 with cache control
MAX_MEM_CACHE_SIZE = 50
_mem_cache: OrderedDict[str, tuple[Optional[ParsedLyrics], Optional[bytes], str]] = OrderedDict()
_mem_lock = threading.Lock()


def _get_from_mem_cache(key: str) -> Optional[tuple[Optional[ParsedLyrics], Optional[bytes], str]]:
    with _mem_lock:
        if key in _mem_cache:
            _mem_cache.move_to_end(key)
            return _mem_cache[key]
    return None


def _put_into_mem_cache(key: str, val: tuple[Optional[ParsedLyrics], Optional[bytes], str]) -> None:
    with _mem_lock:
        if key in _mem_cache:
            _mem_cache.move_to_end(key)
        _mem_cache[key] = val
        while len(_mem_cache) > MAX_MEM_CACHE_SIZE:
            _mem_cache.popitem(last=False)


def _remove_from_mem_cache(key: str) -> None:
    with _mem_lock:
        _mem_cache.pop(key, None)


def fetch_lyrics_multi(
    title: str,
    artist: str,
    on_progress: Optional[Callable[[float], None]] = None,
    on_sub_name: Optional[Callable[[str, str, str], None]] = None,
    on_cover: Optional[Callable[[str, str, bytes], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> tuple[Optional[ParsedLyrics], Optional[bytes], str]:
    """
    多源获取歌词与元信息流水线。
    返回: (parsed_lyrics, hd_cover_bytes, sub_name)
    """
    cache_key = f"{title.lower().strip()}|||{artist.lower().strip()}"
    cached_result = _get_from_mem_cache(cache_key)
    if cached_result is not None:
        if on_progress:
            on_progress(1.0)
        return cached_result

    if on_progress:
        on_progress(0.10)

    # 1. 优先从 SQLite 读取已持久化的干净结构化缓存
    cached_db = db_cache.get_song_cache(title, artist)
    if cached_db and cached_db.get("parsed"):
        parsed = cached_db["parsed"]
        hd_cover = cached_db.get("hd_cover")
        sub_name = cached_db.get("sub_name", "")
        if on_progress:
            on_progress(1.0)
        _put_into_mem_cache(cache_key, (parsed, hd_cover, sub_name))
        return parsed, hd_cover, sub_name

    final_lyrics: Optional[ParsedLyrics] = None
    final_cover: Optional[bytes] = None
    final_sub_name: str = ""

    # 2. 并行获取网易云与 QQ 音乐元数据和歌词
    raw_netease: Optional[RawLyricResult] = None
    item_netease: Optional[SearchSongItem] = None
    cover_netease: Optional[bytes] = None

    raw_qq: Optional[RawLyricResult] = None
    item_qq: Optional[SearchSongItem] = None
    cover_qq: Optional[bytes] = None

    meta_lock = threading.Lock()

    def _update_sub_name(candidate_sub: str, is_qq: bool = False):
        nonlocal final_sub_name
        if not candidate_sub:
            return
        with meta_lock:
            # QQ音乐副标题优先，若已有则仅在更短或来自QQ时更新
            if not final_sub_name:
                final_sub_name = candidate_sub
                if on_sub_name:
                    on_sub_name(title, artist, final_sub_name)
            elif is_qq or len(candidate_sub) < len(final_sub_name):
                final_sub_name = candidate_sub
                if on_sub_name:
                    on_sub_name(title, artist, final_sub_name)

    def _update_cover(candidate_cover: bytes, is_qq: bool = False):
        nonlocal final_cover
        if not candidate_cover or len(candidate_cover) <= 1000:
            return
        with meta_lock:
            # 封面图优先采用 QQ 音乐，若先到了网易云则先展示网易云，QQ 到了再替换
            if not final_cover or is_qq:
                final_cover = candidate_cover
                if on_cover:
                    on_cover(title, artist, final_cover)

    def _is_matching_title(cand_title: str, query_title: str) -> bool:
        if not cand_title or not query_title:
            return True
        import difflib, unicodedata, re
        def _clean(s: str) -> str:
            s = unicodedata.normalize('NFKC', s).lower().strip()
            s = re.sub(r"\(.*?\)|\[.*?\]|（.*?）|【.*?】", "", s)
            s = re.sub(r"\b(?:feat\.?|ft\.?|with)\b.*", "", s, flags=re.IGNORECASE)
            return re.sub(r"[^\w\u4e00-\u9fa5]+", "", s)
        c = _clean(cand_title)
        q = _clean(query_title)
        if not c or not q:
            return True
        if c == q or c in q or q in c:
            return True
        return difflib.SequenceMatcher(None, c, q).ratio() >= 0.60

    def _worker_netease():
        nonlocal raw_netease, item_netease, cover_netease
        try:
            item_netease = NETEASE_PROVIDER.search_song(title, artist)
            if item_netease and not _is_matching_title(item_netease.title, title):
                item_netease = None
            if item_netease and (not is_cancelled or not is_cancelled()):
                if item_netease.sub_name:
                    _update_sub_name(item_netease.sub_name, is_qq=False)
                if item_netease.pic_url:
                    cover_netease = NETEASE_PROVIDER.download_cover(item_netease.pic_url)
                    if cover_netease and (not is_cancelled or not is_cancelled()):
                        _update_cover(cover_netease, is_qq=False)
                raw_netease = NETEASE_PROVIDER.get_lyrics(item_netease)
        except Exception as e:
            print(f"[lyrics_fetcher] netease 并行获取异常: {e}")

    def _worker_qq():
        nonlocal raw_qq, item_qq, cover_qq
        try:
            item_qq = QQMUSIC_PROVIDER.search_song(title, artist)
            if item_qq and not _is_matching_title(item_qq.title, title):
                item_qq = None
            if item_qq and (not is_cancelled or not is_cancelled()):
                if item_qq.sub_name:
                    _update_sub_name(item_qq.sub_name, is_qq=True)
                if item_qq.pic_url:
                    cover_qq = QQMUSIC_PROVIDER.download_cover(item_qq.pic_url)
                    if cover_qq and (not is_cancelled or not is_cancelled()):
                        _update_cover(cover_qq, is_qq=True)
                raw_qq = QQMUSIC_PROVIDER.get_lyrics(item_qq)
        except Exception as e:
            print(f"[lyrics_fetcher] qqmusic 并行获取异常: {e}")

    if on_progress:
        on_progress(0.20)

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_netease = executor.submit(_worker_netease)
        f_qq = executor.submit(_worker_qq)
        f_netease.result()
        f_qq.result()

    if is_cancelled and is_cancelled():
        return None, None, ""

    if on_progress:
        on_progress(0.70)

    # 兜底确保元数据状态一致
    if not final_cover:
        if cover_qq and len(cover_qq) > 1000:
            final_cover = cover_qq
        elif cover_netease and len(cover_netease) > 1000:
            final_cover = cover_netease

    if not final_sub_name:
        if item_qq and item_qq.sub_name:
            final_sub_name = item_qq.sub_name
        elif item_netease and item_netease.sub_name:
            final_sub_name = item_netease.sub_name

    # 【Tier 0】纯音乐快速熔断：若任一平台确认为纯音乐，定性并终止
    is_inst = False
    inst_provider = ""
    inst_id = ""
    if raw_netease and raw_netease.is_instrumental:
        is_inst = True
        inst_provider = raw_netease.provider
        inst_id = raw_netease.song_id
    elif raw_qq and raw_qq.is_instrumental:
        is_inst = True
        inst_provider = raw_qq.provider
        inst_id = raw_qq.song_id
    elif raw_netease and raw_netease.lrc and not raw_netease.yrc:
        check_lrc = parse_raw_bundle(
            lrc_text=raw_netease.lrc,
            title=item_netease.title if item_netease else title,
            artist=item_netease.artist if item_netease else artist,
            provider=raw_netease.provider,
            song_id=raw_netease.song_id,
        )
        if check_lrc.is_instrumental and not check_lrc.lines:
            is_inst = True
            inst_provider = raw_netease.provider
            inst_id = raw_netease.song_id
    elif raw_qq and raw_qq.lrc and not raw_qq.qrc:
        check_qq_lrc = parse_raw_bundle(
            lrc_text=raw_qq.lrc,
            title=item_qq.title if item_qq else title,
            artist=item_qq.artist if item_qq else artist,
            provider=raw_qq.provider,
            song_id=raw_qq.song_id,
        )
        if check_qq_lrc.is_instrumental and not check_qq_lrc.lines:
            is_inst = True
            inst_provider = raw_qq.provider
            inst_id = raw_qq.song_id

    if is_inst:
        final_lyrics = parse_raw_bundle(
            title=item_netease.title if item_netease else (item_qq.title if item_qq else title),
            artist=item_netease.artist if item_netease else (item_qq.artist if item_qq else artist),
            provider=inst_provider,
            song_id=inst_id,
            is_instrumental=True,
        )

    # 【Tier 1】网易云 YRC 逐字
    if not final_lyrics and raw_netease and raw_netease.yrc:
        parsed_netease = parse_raw_bundle(
            yrc_text=raw_netease.yrc,
            tlyric_text=raw_netease.tlyric,
            romalrc_text=raw_netease.romalrc,
            title=item_netease.title if item_netease else title,
            artist=item_netease.artist if item_netease else artist,
            provider=raw_netease.provider,
            song_id=raw_netease.song_id,
            is_instrumental=raw_netease.is_instrumental,
        )
        if parsed_netease.has_words:
            final_lyrics = parsed_netease

    # 【Tier 2】QQ 音乐 QRC 逐字
    if not final_lyrics and raw_qq and raw_qq.qrc:
        cross_trans = raw_qq.tlyric or (raw_netease.tlyric if raw_netease else "")
        cross_roma = raw_qq.romalrc or (raw_netease.romalrc if raw_netease else "")
        parsed_qq = parse_raw_bundle(
            qrc_text=raw_qq.qrc,
            tlyric_text=cross_trans,
            romalrc_text=cross_roma,
            title=item_qq.title if item_qq else title,
            artist=item_qq.artist if item_qq else artist,
            provider=raw_qq.provider,
            song_id=raw_qq.song_id,
            is_instrumental=raw_qq.is_instrumental,
        )
        if parsed_qq.has_words:
            final_lyrics = parsed_qq

    # 【Tier 3】两大平台均无逐字
    if not final_lyrics and raw_netease and (raw_netease.lrc or raw_netease.is_instrumental):
        parsed_netease_lrc = parse_raw_bundle(
            lrc_text=raw_netease.lrc,
            tlyric_text=raw_netease.tlyric,
            romalrc_text=raw_netease.romalrc,
            title=item_netease.title if item_netease else title,
            artist=item_netease.artist if item_netease else artist,
            provider=raw_netease.provider,
            song_id=raw_netease.song_id,
            is_instrumental=raw_netease.is_instrumental,
        )
        if parsed_netease_lrc.lines or parsed_netease_lrc.is_instrumental:
            final_lyrics = parsed_netease_lrc

    # 【Tier 4】退避至 QQ 音乐
    if not final_lyrics and raw_qq and (raw_qq.lrc or raw_qq.is_instrumental):
        cross_trans = raw_qq.tlyric or (raw_netease.tlyric if raw_netease else "")
        cross_roma = raw_qq.romalrc or (raw_netease.romalrc if raw_netease else "")
        parsed_qq_lrc = parse_raw_bundle(
            lrc_text=raw_qq.lrc,
            tlyric_text=cross_trans,
            romalrc_text=cross_roma,
            title=item_qq.title if item_qq else title,
            artist=item_qq.artist if item_qq else artist,
            provider=raw_qq.provider,
            song_id=raw_qq.song_id,
            is_instrumental=raw_qq.is_instrumental,
        )
        if parsed_qq_lrc.lines or parsed_qq_lrc.is_instrumental:
            final_lyrics = parsed_qq_lrc

    # 【Tier 5】前两源均无歌词
    if not final_lyrics:
        try:
            if on_progress:
                on_progress(0.85)
            item_lrclib = LRCLIB_PROVIDER.search_song(title, artist)
            if item_lrclib:
                raw_lrclib = LRCLIB_PROVIDER.get_lyrics(item_lrclib)
                if raw_lrclib and raw_lrclib.lrc:
                    parsed_lrclib = parse_raw_bundle(
                        lrc_text=raw_lrclib.lrc,
                        title=item_lrclib.title or title,
                        artist=item_lrclib.artist or artist,
                        provider=raw_lrclib.provider,
                        song_id=raw_lrclib.song_id,
                        is_instrumental=raw_lrclib.is_instrumental,
                    )
                    if parsed_lrclib.lines or parsed_lrclib.is_instrumental:
                        final_lyrics = parsed_lrclib
        except Exception as e:
            print(f"[lyrics_fetcher] lrclib 获取异常: {e}")

    if on_progress:
        on_progress(1.0)

    # 持久化纯净结构化 JSON
    if final_lyrics:
        db_cache.save_song_cache(
            title=title,
            artist=artist,
            parsed=final_lyrics,
            hd_cover=final_cover,
            sub_name=final_sub_name,
            provider=final_lyrics.provider,
            song_id=final_lyrics.song_id,
        )

    result = (final_lyrics, final_cover, final_sub_name)
    if final_lyrics:
        _put_into_mem_cache(cache_key, result)
    return result


def fetch_and_apply_override(
    track_title: str,
    track_artist: str,
    song_item: SearchSongItem,
    on_progress: Optional[Callable[[float], None]] = None,
    on_sub_name: Optional[Callable[[str, str, str], None]] = None,
    on_cover: Optional[Callable[[str, str, bytes], None]] = None,
) -> tuple[Optional[ParsedLyrics], Optional[bytes], str]:
    """手动指定特定歌曲项并解析、持久化覆盖当前歌曲"""
    if on_progress:
        on_progress(0.2)

    prov = song_item.provider.lower()
    raw_res: Optional[RawLyricResult] = None
    cover_data: Optional[bytes] = None

    if prov == "netease":
        if song_item.pic_url:
            cover_data = NETEASE_PROVIDER.download_cover(song_item.pic_url)
        raw_res = NETEASE_PROVIDER.get_lyrics(song_item)
    elif prov == "qqmusic":
        if song_item.pic_url:
            cover_data = QQMUSIC_PROVIDER.download_cover(song_item.pic_url)
        raw_res = QQMUSIC_PROVIDER.get_lyrics(song_item)
    elif prov == "lrclib":
        raw_res = LRCLIB_PROVIDER.get_lyrics(song_item)

    if on_progress:
        on_progress(0.7)

    parsed_lyrics: Optional[ParsedLyrics] = None
    sub_name = song_item.sub_name or (raw_res.sub_name if raw_res else "")

    if raw_res:
        if raw_res.cover_data and not cover_data:
            cover_data = raw_res.cover_data
        parsed_lyrics = parse_raw_bundle(
            yrc_text=raw_res.yrc,
            qrc_text=raw_res.qrc,
            lrc_text=raw_res.lrc,
            tlyric_text=raw_res.tlyric,
            romalrc_text=raw_res.romalrc,
            title=song_item.title or track_title,
            artist=song_item.artist or track_artist,
            provider=song_item.provider,
            song_id=song_item.song_id,
            is_instrumental=raw_res.is_instrumental,
        )

    if on_sub_name and sub_name:
        on_sub_name(track_title, track_artist, sub_name)
    if on_cover and cover_data:
        on_cover(track_title, track_artist, cover_data)

    if parsed_lyrics:
        # 直接更新数据库本地缓存与内存缓存
        db_cache.save_song_cache(
            title=track_title,
            artist=track_artist,
            parsed=parsed_lyrics,
            hd_cover=cover_data,
            sub_name=sub_name,
            provider=song_item.provider,
            song_id=song_item.song_id,
        )
        cache_key = f"{track_title.lower().strip()}|||{track_artist.lower().strip()}"
        _put_into_mem_cache(cache_key, (parsed_lyrics, cover_data, sub_name))

    if on_progress:
        on_progress(1.0)

    return parsed_lyrics, cover_data, sub_name


def clear_song_cache(title: str, artist: str = "") -> None:
    """清除当前歌曲的数据库本地缓存与内存缓存"""
    db_cache.delete_song_cache(title, artist)
    cache_key = f"{title.lower().strip()}|||{artist.lower().strip()}"
    _remove_from_mem_cache(cache_key)


def search_all_sources(
    title: str,
    artist: str = "",
    provider_filter: str = "all",
    limit: int = 15
) -> list[SearchSongItem]:
    """聚合搜索"""
    prov = (provider_filter or "all").lower().strip()
    if prov != "all":
        if prov == "netease":
            return NETEASE_PROVIDER.search_songs(title, artist, limit=limit)
        elif prov == "qqmusic":
            return QQMUSIC_PROVIDER.search_songs(title, artist, limit=limit)
        elif prov == "lrclib":
            return LRCLIB_PROVIDER.search_songs(title, artist, limit=limit)
        return []

    results: list[SearchSongItem] = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        f_wy = executor.submit(NETEASE_PROVIDER.search_songs, title, artist, limit)
        f_qq = executor.submit(QQMUSIC_PROVIDER.search_songs, title, artist, limit)
        f_lrc = executor.submit(LRCLIB_PROVIDER.search_songs, title, artist, limit)

        for f in (f_wy, f_qq, f_lrc):
            try:
                items = f.result()
                if items:
                    results.extend(items)
            except Exception as e:
                print(f"[lyrics_fetcher] 并行 search_songs 异常: {e}")

    return results
