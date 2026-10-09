"""
LyrikFlow Core Package
包含 SMTC 监听、歌词获取、解析、本地缓存、字体管理和配置设置。
"""
from __future__ import annotations

from .settings import (
    get_opacity, set_opacity,
    get_font_size_current, set_font_size_current,
    get_font_size_context, set_font_size_context,
    get_fullscreen_context_lines, set_fullscreen_context_lines,
    get_show_translation, set_show_translation,
    get_show_line_progress, set_show_line_progress,
    get_watched_apps, set_watched_apps,
    get_mode, set_mode,
    get_overlay_geometry, set_overlay_geometry,
    get_offset_ms, set_offset_ms,
    get_font_configs, set_font_configs,
)
from .font_manager import (
    FontItem,
    scan_fonts,
    make_app_font,
    open_fonts_folder,
    get_fonts_dir,
    get_font_items,
    save_font_items,
    get_effective_font_families,
    get_font_css_family,
    get_font_sample_text,
)
from .db_cache import (
    init_db,
    make_track_key,
    get_song_cache,
    save_song_cache,
    DATA_DIR,
    DB_PATH,
)
from .lyrics_fetcher import (
    get_lyrics_bundle,
    get_lyrics,
)
from .lyrics_parser import (
    ParsedLyrics,
    LyricLine,
    LyricWord,
    parse,
    parse_bundle,
    parse_yrc,
    parse_lrc,
)
from .smtc_listener import SMTCListener

__all__ = [
    # settings
    "get_opacity", "set_opacity",
    "get_font_size_current", "set_font_size_current",
    "get_font_size_context", "set_font_size_context",
    "get_fullscreen_context_lines", "set_fullscreen_context_lines",
    "get_show_translation", "set_show_translation",
    "get_show_line_progress", "set_show_line_progress",
    "get_watched_apps", "set_watched_apps",
    "get_mode", "set_mode",
    "get_overlay_geometry", "set_overlay_geometry",
    "get_offset_ms", "set_offset_ms",
    "get_font_configs", "set_font_configs",
    # font_manager
    "FontItem", "scan_fonts", "make_app_font", "open_fonts_folder", "get_fonts_dir",
    "get_font_items", "save_font_items", "get_effective_font_families", "get_font_css_family",
    "get_font_sample_text",
    # db_cache
    "init_db", "make_track_key", "get_song_cache", "save_song_cache", "DATA_DIR", "DB_PATH",
    # lyrics_fetcher
    "get_lyrics_bundle", "get_lyrics",
    # lyrics_parser
    "ParsedLyrics", "LyricLine", "LyricWord", "parse", "parse_bundle", "parse_yrc", "parse_lrc",
    # smtc_listener
    "SMTCListener",
]
