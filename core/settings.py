"""
settings.py — 用户设置管理
"""
from __future__ import annotations

import copy
import json
import os
import threading
import sys
from typing import Any, Optional
import yaml

# 项目根目录与配置文件路径
def get_base_dir() -> str:
    nuitka_bin = os.environ.get("NUITKA_ONEFILE_BINARY")
    if nuitka_bin:
        return os.path.dirname(os.path.abspath(nuitka_bin))

    if getattr(sys, "frozen", False) or "__compiled__" in globals() or hasattr(sys, "_MEIPASS"):
        if sys.argv and sys.argv[0] and os.path.isfile(os.path.abspath(sys.argv[0])):
            return os.path.dirname(os.path.abspath(sys.argv[0]))
        return os.path.dirname(os.path.abspath(sys.executable))

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = get_base_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")


def get_config_path() -> str:
    return os.path.join(DATA_DIR, "config.yaml")


DEFAULT_CONFIG: dict[str, Any] = {
    "window": {
        "mode": "overlay",
    },
    "overlay": {
        "opacity": 0.85,
        "x": -1,
        "y": -1,
        "w": 900,
        "h": 130,
    },
    "font": {
        "size_current": 28,
        "size_context": 14,
        "configs": [],
    },
    "lyrics": {
        "show_translation": True,
        "show_romaji": False,
        "secondary_mode": "prefer_trans",
        "show_line_progress": True,
        "offset_ms": 0,
        "parse_sections": True,
    },
    "fullscreen": {
        "context_lines": 5,
        "font_size_current": 38,
        "font_size_context": 18,
        "context_secondary_mode": "both",
    },
    "smtc": {
        "watched_apps": ["cloudmusic.exe"],
    },
    "theme": {
        "preset": "classic",
        "seed_color": "#0B57D0",
        "colors": {
            "lyric_active": "#FFFFFF",
            "lyric_inactive": "#A0A8B8",
            "lyric_secondary": "#C3E1FF",
            "progress_start": "#FFFFFF",
            "progress_end": "#A0E6FF",
            "accent": "#78CDFF",
        },
    },
}

_lock = threading.RLock()
_CACHE: Optional[dict[str, Any]] = None


def _filter_valid_config(schema: dict, user_data: dict) -> dict:
    res = {}
    for k, def_val in schema.items():
        if k in user_data:
            val = user_data[k]
            if isinstance(def_val, dict) and isinstance(val, dict):
                res[k] = _filter_valid_config(def_val, val)
            else:
                res[k] = copy.deepcopy(val)
        else:
            res[k] = copy.deepcopy(def_val)
    return res


def _get_config() -> dict[str, Any]:
    global _CACHE
    with _lock:
        if _CACHE is not None:
            return _CACHE

        cfg_path = get_config_path()
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict):
                    _CACHE = _filter_valid_config(DEFAULT_CONFIG, data)
                else:
                    _CACHE = copy.deepcopy(DEFAULT_CONFIG)
            except Exception as e:
                print(f"[Settings] 读取 YAML 配置文件失败: {e}，将采用默认配置")
                _CACHE = copy.deepcopy(DEFAULT_CONFIG)
        else:
            _CACHE = copy.deepcopy(DEFAULT_CONFIG)
            _save_config_locked()

        return _CACHE


def _save_config_locked() -> None:
    global _CACHE
    if _CACHE is None:
        return
    cfg_path = get_config_path()
    try:
        os.makedirs(os.path.dirname(os.path.abspath(cfg_path)), exist_ok=True)
        tmp_path = cfg_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(_CACHE, f, allow_unicode=True, sort_keys=False, default_flow_style=False, indent=2)
        if os.path.exists(tmp_path):
            if os.path.exists(cfg_path):
                os.replace(tmp_path, cfg_path)
            else:
                os.rename(tmp_path, cfg_path)
    except Exception as e:
        print(f"[Settings] 保存 YAML 配置文件失败: {e}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def _get(keys: list[str], default: Any) -> Any:
    cfg = _get_config()
    curr: Any = cfg
    for k in keys:
        if isinstance(curr, dict) and k in curr:
            curr = curr[k]
        else:
            return default
    return curr


def _set(keys: list[str], val: Any) -> None:
    with _lock:
        curr = _get_config()
        for k in keys[:-1]:
            if k not in curr or not isinstance(curr[k], dict):
                curr[k] = {}
            curr = curr[k]
        curr[keys[-1]] = val
        _save_config_locked()


# ── 读取接口 ─────────────────────────────────────────────────────────────────
def get_opacity() -> float:
    return float(_get(["overlay", "opacity"], 0.85))

def get_font_size_current() -> int:
    val = _get(["font", "size_current"], 28)
    try:
        val = int(val)
        return val if val > 0 else 28
    except Exception:
        return 28

def get_font_size_context() -> int:
    val = _get(["font", "size_context"], 14)
    try:
        val = int(val)
        return val if val > 0 else 14
    except Exception:
        return 14

def get_fullscreen_context_lines() -> int:
    """全屏模式下当前歌词上下各显示的上下文行数（默认 5 行）"""
    val = _get(["fullscreen", "context_lines"], 5)
    try:
        return max(1, min(10, int(val)))
    except Exception:
        return 5

def get_fullscreen_font_size_current() -> int:
    """全屏模式下当前行歌词字号（默认 38）"""
    val = _get(["fullscreen", "font_size_current"], 38)
    try:
        val = int(val)
        return val if val > 0 else 38
    except Exception:
        return 38

def get_fullscreen_font_size_context() -> int:
    """全屏模式下上下文歌词字号（默认 18）"""
    val = _get(["fullscreen", "font_size_context"], 18)
    try:
        val = int(val)
        return val if val > 0 else 18
    except Exception:
        return 18

def get_fullscreen_context_secondary_mode() -> str:
    """全屏非当前行副行显示内容"""
    return str(_get(["fullscreen", "context_secondary_mode"], "both"))

def get_show_translation() -> bool:
    return bool(_get(["lyrics", "show_translation"], True))

def get_show_romaji() -> bool:
    return bool(_get(["lyrics", "show_romaji"], False))

def get_secondary_mode() -> str:
    """副行显示偏好"""
    return str(_get(["lyrics", "secondary_mode"], "prefer_trans"))

def get_show_line_progress() -> bool:
    """无逐字歌词时是否在当前行下方显示单句进度条"""
    return bool(_get(["lyrics", "show_line_progress"], True))

def get_parse_sections() -> bool:
    """是否开启段落解析"""
    return bool(_get(["lyrics", "parse_sections"], True))

def get_watched_apps() -> list[str]:
    val = _get(["smtc", "watched_apps"], ["cloudmusic.exe"])
    if isinstance(val, list):
        return [str(v).strip() for v in val if str(v).strip()]
    if isinstance(val, str):
        return [v.strip() for v in val.split(",") if v.strip()]
    return ["cloudmusic.exe"]

def get_mode() -> str:
    """返回 'overlay' 或 'fullscreen'"""
    return str(_get(["window", "mode"], "overlay"))

def get_overlay_geometry() -> tuple[int, int, int, int] | None:
    """返回 (x, y, w, h) 或 None"""
    try:
        x = int(_get(["overlay", "x"], -1))
        y = int(_get(["overlay", "y"], -1))
        w = int(_get(["overlay", "w"], 900))
        h = int(_get(["overlay", "h"], 130))
        if x < 0 or y < 0:
            return None
        return x, y, w, h
    except Exception:
        return None

def get_offset_ms() -> int:
    return int(_get(["lyrics", "offset_ms"], 0))

def make_song_key(title: str, artist: str = "") -> str:
    """生成标准化且易读的歌曲键名"""
    t = str(title or "").strip()
    a = str(artist or "").strip()
    return f"{t} - {a}" if a else t

def get_song_offsets() -> dict[str, int]:
    """读取所有单独配置的歌曲偏移字典"""
    try:
        from core import db_cache
        return db_cache.get_all_song_offsets()
    except Exception:
        return {}

def get_song_offset(title: str, artist: str = "") -> Optional[int]:
    """获取指定歌曲的单独偏移量"""
    if not title:
        return None
    try:
        from core import db_cache
        return db_cache.get_song_offset(title, artist)
    except Exception:
        return None

def get_effective_song_offset(title: str, artist: str = "") -> int:
    """获取指定歌曲的最终生效偏移量"""
    val = get_song_offset(title, artist)
    if val is not None:
        return val
    return get_offset_ms()

def get_font_configs() -> list[dict]:
    """读取保存的字体配置列表 [{'family': str, 'enabled': bool}]"""
    val = _get(["font", "configs"], [])
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val:
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return []


# ── 写入接口 ─────────────────────────────────────────────────────────────────
def set_opacity(v: float) -> None:
    _set(["overlay", "opacity"], max(0.15, min(1.0, float(v))))

def set_font_size_current(v: int) -> None:
    _set(["font", "size_current"], int(v))

def set_font_size_context(v: int) -> None:
    _set(["font", "size_context"], int(v))

def set_fullscreen_context_lines(v: int) -> None:
    _set(["fullscreen", "context_lines"], max(1, min(10, int(v))))

def set_fullscreen_font_size_current(v: int) -> None:
    _set(["fullscreen", "font_size_current"], max(12, min(96, int(v))))

def set_fullscreen_font_size_context(v: int) -> None:
    _set(["fullscreen", "font_size_context"], max(8, min(64, int(v))))

def set_fullscreen_context_secondary_mode(v: str) -> None:
    if v not in ("none", "translation", "romaji", "both"):
        v = "both"
    _set(["fullscreen", "context_secondary_mode"], str(v))

def set_show_translation(v: bool) -> None:
    _set(["lyrics", "show_translation"], bool(v))

def set_show_romaji(v: bool) -> None:
    _set(["lyrics", "show_romaji"], bool(v))

def set_secondary_mode(v: str) -> None:
    _set(["lyrics", "secondary_mode"], str(v))

def set_show_line_progress(v: bool) -> None:
    _set(["lyrics", "show_line_progress"], bool(v))

def set_parse_sections(v: bool) -> None:
    _set(["lyrics", "parse_sections"], bool(v))

def set_watched_apps(apps: list[str]) -> None:
    _set(["smtc", "watched_apps"], [str(a).strip() for a in apps if str(a).strip()])

def set_mode(v: str) -> None:
    _set(["window", "mode"], str(v))

def set_overlay_geometry(x: int, y: int, w: int, h: int) -> None:
    with _lock:
        cfg = _get_config()
        if "overlay" not in cfg or not isinstance(cfg["overlay"], dict):
            cfg["overlay"] = {}
        cfg["overlay"]["x"] = int(x)
        cfg["overlay"]["y"] = int(y)
        cfg["overlay"]["w"] = int(w)
        cfg["overlay"]["h"] = int(h)
        _save_config_locked()

def set_offset_ms(v: int) -> None:
    _set(["lyrics", "offset_ms"], int(v))

def set_song_offset(title: str, artist: str = "", offset_ms: int = 0) -> None:
    """设置单首歌曲的独立偏移量并持久化到 SQLite 数据库"""
    if not title:
        return
    try:
        from core import db_cache
        db_cache.set_song_offset(title, artist, int(offset_ms))
    except Exception as e:
        print(f"[Settings] 设置歌曲独立偏移异常: {e}")

def remove_song_offset(title: str, artist: str = "") -> None:
    """移除单首歌曲的独立偏移量配置（从 SQLite 数据库）"""
    if not title:
        return
    try:
        from core import db_cache
        db_cache.remove_song_offset(title, artist)
    except Exception as e:
        print(f"[Settings] 移除歌曲独立偏移异常: {e}")

def set_all_song_offsets(offsets: dict[str, int]) -> None:
    """全量更新 SQLite 数据库中的歌曲独立偏移字典"""
    try:
        from core import db_cache
        db_cache.set_all_song_offsets(offsets)
    except Exception as e:
        print(f"[Settings] 全量更新歌曲独立偏移异常: {e}")

def set_font_configs(configs: list[dict]) -> None:
    """保存字体配置列表"""
    _set(["font", "configs"], configs)


# ── 主题与配色方案接口 ────────────────────────────────────────────────────────
def get_theme_preset() -> str:
    """获取当前选择的配色预设名称 ('classic', 'md_blue', 'sakura', 'custom' 等)"""
    return str(_get(["theme", "preset"], "classic"))

def set_theme_preset(v: str) -> None:
    """保存当前选择的配色预设名称"""
    _set(["theme", "preset"], str(v))

def get_theme_seed_color() -> str:
    """获取 MD 种子颜色 (例如 '#0B57D0')"""
    return str(_get(["theme", "seed_color"], "#0B57D0"))

def set_theme_seed_color(v: str) -> None:
    """保存 MD 种子颜色"""
    _set(["theme", "seed_color"], str(v))

def get_theme_colors() -> dict[str, str]:
    """获取当前生效的歌词各角色颜色字典"""
    from core.color_theme import get_default_colors
    val = _get(["theme", "colors"], None)
    default_colors = get_default_colors()
    if isinstance(val, dict):
        res = dict(default_colors)
        res.update({str(k): str(v) for k, v in val.items() if v})
        return res
    return default_colors

def set_theme_colors(colors: dict[str, str]) -> None:
    """全量更新歌词各角色颜色配置"""
    _set(["theme", "colors"], {str(k): str(v) for k, v in colors.items() if v})

def get_theme_color(role: str, default: str = "#FFFFFF") -> str:
    """获取指定角色的十六进制颜色字符串"""
    colors = get_theme_colors()
    return colors.get(role, default)
