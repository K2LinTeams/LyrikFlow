"""
core/providers/base.py — 歌词提供源基础抽象类与数据模型
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchSongItem:
    """搜索匹配到的单曲元信息"""
    song_id: str                      # 平台歌曲唯一 ID (网易云 id, QQ 音乐 numeric musicid / mid)
    title: str                        # 歌名
    artist: str                       # 歌手
    album: str = ""                   # 专辑名
    duration_ms: int = 0              # 时长 (毫秒)
    pic_url: Optional[str] = None     # 封面链接
    sub_name: str = ""                # 别名/副标题
    provider: str = ""                # 提供源标识 (netease, qqmusic, lrclib)
    song_mid: str = ""                # QQ 音乐专属 string mid (如 001p3V4c0PQdmd)


@dataclass
class RawLyricResult:
    """提供源获取到的原始歌词文本与素材包"""
    provider: str
    song_id: str
    title: str
    artist: str
    sub_name: str = ""
    yrc: str = ""                     # 网易云 YRC 逐字歌词文本
    qrc: str = ""                     # QQ 音乐 QRC 逐字歌词文本
    lrc: str = ""                     # 标准 LRC 歌词文本
    tlyric: str = ""                  # 翻译 LRC 歌词文本
    romalrc: str = ""                 # 罗马音歌词文本
    pic_url: Optional[str] = None     # 专辑封面网络 URL
    cover_data: Optional[bytes] = None# 已下载的高清封面二进制
    is_instrumental: bool = False     # 平台标记纯音乐


class BaseLyricProvider:
    """歌词提供源基础抽象类"""

    provider_name: str = "base"

    def search_song(self, title: str, artist: str) -> Optional[SearchSongItem]:
        """根据歌名和歌手搜索最匹配的歌曲"""
        raise NotImplementedError

    def get_lyrics(self, song_item: SearchSongItem) -> Optional[RawLyricResult]:
        """根据歌曲信息获取歌词与素材"""
        raise NotImplementedError

    def download_cover(self, pic_url: str) -> Optional[bytes]:
        """下载高清封面二进制"""
        return None
