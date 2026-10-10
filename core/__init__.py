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
    get_fullscreen_font_size_current, set_fullscreen_font_size_current,
    get_fullscreen_font_size_context, set_fullscreen_font_size_context,
    get_show_translation, set_show_translation,
    get_show_romaji, set_show_romaji,
    get_secondary_mode, set_secondary_mode,
    get_show_line_progress, set_show_line_progress,
    get_watched_apps, set_watched_apps,
    get_mode, set_mode,
    get_overlay_geometry, set_overlay_geometry,
    get_offset_ms, set_offset_ms,
    make_song_key, get_song_offsets, get_song_offset, get_effective_song_offset,
    set_song_offset, remove_song_offset, set_all_song_offsets,
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
    update_song_offset,
    get_song_offset as get_db_song_offset,
    get_all_song_offsets as get_all_db_song_offsets,
    set_song_offset as set_db_song_offset,
    remove_song_offset as remove_db_song_offset,
    set_all_song_offsets as set_all_db_song_offsets,
    DATA_DIR,
    DB_PATH,
)
from .lyrics_fetcher import (
    fetch_lyrics_multi,
)
from .lyrics_parser import (
    ParsedLyrics,
    LyricLine,
    LyricWord,
    parse_raw_bundle,
    parse_yrc,
    parse_qrc,
    parse_lrc,
)
from .smtc_listener import SMTCListener

__all__ = [
    # settings
    "get_opacity", "set_opacity",
    "get_font_size_current", "set_font_size_current",
    "get_font_size_context", "set_font_size_context",
    "get_fullscreen_context_lines", "set_fullscreen_context_lines",
    "get_fullscreen_font_size_current", "set_fullscreen_font_size_current",
    "get_fullscreen_font_size_context", "set_fullscreen_font_size_context",
    "get_show_translation", "set_show_translation",
    "get_show_romaji", "set_show_romaji",
    "get_secondary_mode", "set_secondary_mode",
    "get_show_line_progress", "set_show_line_progress",
    "get_watched_apps", "set_watched_apps",
    "get_mode", "set_mode",
    "get_overlay_geometry", "set_overlay_geometry",
    "get_offset_ms", "set_offset_ms",
    "make_song_key", "get_song_offsets", "get_song_offset", "get_effective_song_offset",
    "set_song_offset", "remove_song_offset", "set_all_song_offsets",
    "get_font_configs", "set_font_configs",
    # font_manager
    "FontItem", "scan_fonts", "make_app_font", "open_fonts_folder", "get_fonts_dir",
    "get_font_items", "save_font_items", "get_effective_font_families", "get_font_css_family",
    "get_font_sample_text",
    # db_cache
    "init_db", "make_track_key", "get_song_cache", "save_song_cache", "update_song_offset", "DATA_DIR", "DB_PATH",
    # lyrics_fetcher
    "fetch_lyrics_multi",
    # lyrics_parser
    "ParsedLyrics", "LyricLine", "LyricWord", "parse_raw_bundle", "parse_yrc", "parse_qrc", "parse_lrc",
    # smtc_listener
    "SMTCListener",
]
