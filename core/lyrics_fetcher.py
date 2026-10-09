"""
core/lyrics_fetcher.py — 多源歌词获取
"""
from __future__ import annotations

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

# 内存快速缓存：(title, artist) -> (ParsedLyrics, cover_bytes, sub_name)
_mem_cache: dict[str, tuple[Optional[ParsedLyrics], Optional[bytes], str]] = {}


def fetch_lyrics_multi(
    title: str,
    artist: str,
    on_progress: Optional[Callable[[float], None]] = None,
    on_sub_name: Optional[Callable[[str, str, str], None]] = None,
    on_cover: Optional[Callable[[str, str, bytes], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> tuple[Optional[ParsedLyrics], Optional[bytes], str]:
    """
    多源获取歌词与元信息完整流水线。
    返回: (parsed_lyrics, hd_cover_bytes, sub_name)
    """
    cache_key = f"{title.lower().strip()}|||{artist.lower().strip()}"
    if cache_key in _mem_cache:
        cached_result = _mem_cache[cache_key]
        if on_progress:
            on_progress(1.0)
        return cached_result

    if on_progress:
        on_progress(0.10)

    # 1. 优先从 SQLite 读取已持久化的干净结构化缓存 (0ms 零解析)
    cached_db = db_cache.get_song_cache(title, artist)
    if cached_db and cached_db.get("parsed"):
        parsed = cached_db["parsed"]
        hd_cover = cached_db.get("hd_cover")
        sub_name = cached_db.get("sub_name", "")
        if on_progress:
            on_progress(1.0)
        _mem_cache[cache_key] = (parsed, hd_cover, sub_name)
        return parsed, hd_cover, sub_name

    final_lyrics: Optional[ParsedLyrics] = None
    final_cover: Optional[bytes] = None
    final_sub_name: str = ""

    # 2. 查询网易云音乐
    raw_netease: Optional[RawLyricResult] = None
    item_netease: Optional[SearchSongItem] = None
    try:
        if on_progress:
            on_progress(0.25)
        item_netease = NETEASE_PROVIDER.search_song(title, artist)
        if item_netease:
            if item_netease.sub_name and not final_sub_name:
                final_sub_name = item_netease.sub_name
                if on_sub_name:
                    on_sub_name(title, artist, final_sub_name)

            if item_netease.pic_url and not final_cover:
                c = NETEASE_PROVIDER.download_cover(item_netease.pic_url)
                if c:
                    final_cover = c
                    if on_cover:
                        on_cover(title, artist, c)

            raw_netease = NETEASE_PROVIDER.get_lyrics(item_netease)
    except Exception as e:
        print(f"[lyrics_fetcher] netease 获取异常: {e}")

    if is_cancelled and is_cancelled():
        return None, None, ""

    # 【Tier 0】纯音乐快速熔断：若网易云确认为纯音乐，立即定性并短路终止后续所有平台查询
    is_netease_inst = False
    if raw_netease:
        if raw_netease.is_instrumental:
            is_netease_inst = True
        elif raw_netease.lrc and not raw_netease.yrc:
            check_lrc = parse_raw_bundle(
                lrc_text=raw_netease.lrc,
                title=item_netease.title if item_netease else title,
                artist=item_netease.artist if item_netease else artist,
                provider=raw_netease.provider,
                song_id=raw_netease.song_id,
            )
            if check_lrc.is_instrumental and not check_lrc.lines:
                is_netease_inst = True

    if is_netease_inst and raw_netease:
        final_lyrics = parse_raw_bundle(
            title=item_netease.title if item_netease else title,
            artist=item_netease.artist if item_netease else artist,
            provider=raw_netease.provider,
            song_id=raw_netease.song_id,
            is_instrumental=True,
        )

    # 【Tier 1】优先：网易云 (YRC 逐字)
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

    # 【Tier 2】网易云无逐字且非纯音乐，退避至 QQ 音乐 (QRC 逐字)
    raw_qq: Optional[RawLyricResult] = None
    item_qq: Optional[SearchSongItem] = None
    if not final_lyrics:
        try:
            if on_progress:
                on_progress(0.55)
            item_qq = QQMUSIC_PROVIDER.search_song(title, artist)
            if item_qq:
                if item_qq.sub_name:
                    if not final_sub_name:
                        final_sub_name = item_qq.sub_name
                        if on_sub_name:
                            on_sub_name(title, artist, final_sub_name)
                    elif len(item_qq.sub_name) < len(final_sub_name):
                        final_sub_name = item_qq.sub_name
                        if on_sub_name:
                            on_sub_name(title, artist, final_sub_name)

                if item_qq.pic_url and not final_cover:
                    c = QQMUSIC_PROVIDER.download_cover(item_qq.pic_url)
                    if c:
                        final_cover = c
                        if on_cover:
                            on_cover(title, artist, c)

                raw_qq = QQMUSIC_PROVIDER.get_lyrics(item_qq)
        except Exception as e:
            print(f"[lyrics_fetcher] qqmusic 获取异常: {e}")

        if is_cancelled and is_cancelled():
            return None, None, ""

        if raw_qq:
            # QQ 音乐纯音乐短路熔断
            is_qq_inst = False
            if raw_qq.is_instrumental:
                is_qq_inst = True
            elif raw_qq.lrc and not raw_qq.qrc:
                check_lrc = parse_raw_bundle(
                    lrc_text=raw_qq.lrc,
                    title=item_qq.title if item_qq else title,
                    artist=item_qq.artist if item_qq else artist,
                    provider=raw_qq.provider,
                    song_id=raw_qq.song_id,
                )
                if check_lrc.is_instrumental and not check_lrc.lines:
                    is_qq_inst = True

            if is_qq_inst:
                final_lyrics = parse_raw_bundle(
                    title=item_qq.title if item_qq else title,
                    artist=item_qq.artist if item_qq else artist,
                    provider=raw_qq.provider,
                    song_id=raw_qq.song_id,
                    is_instrumental=True,
                )
            elif raw_qq.qrc:
                parsed_qq = parse_raw_bundle(
                    qrc_text=raw_qq.qrc,
                    tlyric_text=raw_qq.tlyric,
                    romalrc_text=raw_qq.romalrc,
                    title=item_qq.title if item_qq else title,
                    artist=item_qq.artist if item_qq else artist,
                    provider=raw_qq.provider,
                    song_id=raw_qq.song_id,
                    is_instrumental=raw_qq.is_instrumental,
                )
                if parsed_qq.has_words:
                    final_lyrics = parsed_qq

    # 【Tier 3】两大平台均无逐字，退避至 网易云 (LRC + 译文)
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

    # 【Tier 4】网易云无歌词，退避至 QQ 音乐 (LRC + 译文)
    if not final_lyrics and raw_qq and (raw_qq.lrc or raw_qq.is_instrumental):
        parsed_qq_lrc = parse_raw_bundle(
            lrc_text=raw_qq.lrc,
            tlyric_text=raw_qq.tlyric,
            romalrc_text=raw_qq.romalrc,
            title=item_qq.title if item_qq else title,
            artist=item_qq.artist if item_qq else artist,
            provider=raw_qq.provider,
            song_id=raw_qq.song_id,
            is_instrumental=raw_qq.is_instrumental,
        )
        if parsed_qq_lrc.lines or parsed_qq_lrc.is_instrumental:
            final_lyrics = parsed_qq_lrc

    # 【Tier 5】前两源均无歌词，最后尝试 LRCLIB 备用兜底
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
        _mem_cache[cache_key] = result
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
        _mem_cache[cache_key] = (parsed_lyrics, cover_data, sub_name)

    if on_progress:
        on_progress(1.0)

    return parsed_lyrics, cover_data, sub_name


def clear_song_cache(title: str, artist: str = "") -> None:
    """清除当前歌曲的数据库本地缓存与内存缓存"""
    db_cache.delete_song_cache(title, artist)
    cache_key = f"{title.lower().strip()}|||{artist.lower().strip()}"
    _mem_cache.pop(cache_key, None)


def search_all_sources(
    title: str,
    artist: str = "",
    provider_filter: str = "all",
    limit: int = 15
) -> list[SearchSongItem]:
    """多源聚合搜索候选歌曲列表"""
    prov = (provider_filter or "all").lower().strip()
    results: list[SearchSongItem] = []

    if prov in ("all", "netease"):
        try:
            items = NETEASE_PROVIDER.search_songs(title, artist, limit=limit)
            results.extend(items)
        except Exception as e:
            print(f"[lyrics_fetcher] netease search_songs 异常: {e}")

    if prov in ("all", "qqmusic"):
        try:
            items = QQMUSIC_PROVIDER.search_songs(title, artist, limit=limit)
            results.extend(items)
        except Exception as e:
            print(f"[lyrics_fetcher] qqmusic search_songs 异常: {e}")

    if prov in ("all", "lrclib"):
        try:
            items = LRCLIB_PROVIDER.search_songs(title, artist, limit=limit)
            results.extend(items)
        except Exception as e:
            print(f"[lyrics_fetcher] lrclib search_songs 异常: {e}")

    return results
