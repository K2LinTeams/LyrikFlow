"""
core/providers/__init__.py — 歌词提供源模块
"""
from __future__ import annotations

from .base import BaseLyricProvider, RawLyricResult, SearchSongItem
from .netease import NeteaseLyricProvider
from .qqmusic import QQMusicLyricProvider
from .lrclib import LrclibLyricProvider

__all__ = [
    "BaseLyricProvider",
    "RawLyricResult",
    "SearchSongItem",
    "NeteaseLyricProvider",
    "QQMusicLyricProvider",
    "LrclibLyricProvider",
]
