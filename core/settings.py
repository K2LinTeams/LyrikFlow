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
    """获取根目录"""
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = get_base_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")


def get_config_path() -> str:
    """获取配置文件路径"""
    root_cfg = os.path.join(BASE_DIR, "config.yaml")
    data_cfg = os.path.join(DATA_DIR, "config.yaml")
    if os.path.isfile(data_cfg) and not os.path.isfile(root_cfg):
        return data_cfg
    return root_cfg


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
    },
    "smtc": {
        "watched_apps": ["cloudmusic.exe"],
    },
}

_lock = threading.RLock()
_CACHE: Optional[dict[str, Any]] = None


def _deep_merge(base: dict, update: dict) -> dict:
    """深度合并字典，保留 base 中的默认键"""
    res = copy.deepcopy(base)
    for k, v in update.items():
        if k in res and isinstance(res[k], dict) and isinstance(v, dict):
            res[k] = _deep_merge(res[k], v)
        else:
            res[k] = copy.deepcopy(v)
    return res


def _migrate_from_qsettings(cfg: dict[str, Any]) -> dict[str, Any]:
    """尝试从系统历史 QSettings (注册表) 迁移旧配置"""
    try:
        from PyQt6.QtCore import QSettings
        s = QSettings("LyrikFlow", "LyrikFlow")
        keys = s.allKeys()
        if not keys:
            return cfg

        # 悬浮窗透明度
        if "overlay/opacity" in keys:
            try:
                cfg["overlay"]["opacity"] = float(s.value("overlay/opacity"))
            except Exception:
                pass

        # 悬浮窗位置大小
        if "overlay/x" in keys:
            try:
                cfg["overlay"]["x"] = int(s.value("overlay/x"))
                cfg["overlay"]["y"] = int(s.value("overlay/y"))
                cfg["overlay"]["w"] = int(s.value("overlay/w"))
                cfg["overlay"]["h"] = int(s.value("overlay/h"))
            except Exception:
                pass

        # 字号
        if "font/size_current" in keys:
            try:
                cfg["font"]["size_current"] = int(s.value("font/size_current"))
            except Exception:
                pass

        if "font/size_context" in keys:
            try:
                cfg["font"]["size_context"] = int(s.value("font/size_context"))
            except Exception:
                pass

        # 字体配置
        if "font/configs" in keys:
            raw = s.value("font/configs")
            if raw:
                try:
                    parsed = json.loads(str(raw)) if isinstance(raw, str) else raw
                    if isinstance(parsed, list):
                        cfg["font"]["configs"] = parsed
                except Exception:
                    pass

        # 歌词设置
        if "lyrics/show_translation" in keys:
            raw_tr = s.value("lyrics/show_translation")
            if isinstance(raw_tr, str):
                cfg["lyrics"]["show_translation"] = raw_tr.lower() in ("true", "1")
            else:
                cfg["lyrics"]["show_translation"] = bool(raw_tr)

        if "lyrics/show_romaji" in keys:
            raw_ro = s.value("lyrics/show_romaji")
            if isinstance(raw_ro, str):
                cfg["lyrics"]["show_romaji"] = raw_ro.lower() in ("true", "1")
            else:
                cfg["lyrics"]["show_romaji"] = bool(raw_ro)

        if "lyrics/secondary_mode" in keys:
            cfg["lyrics"]["secondary_mode"] = str(s.value("lyrics/secondary_mode"))

        if "lyrics/offset_ms" in keys:
            try:
                cfg["lyrics"]["offset_ms"] = int(s.value("lyrics/offset_ms"))
            except Exception:
                pass

        if "lyrics/parse_sections" in keys:
            raw_ps = s.value("lyrics/parse_sections")
            if isinstance(raw_ps, str):
                cfg["lyrics"]["parse_sections"] = raw_ps.lower() in ("true", "1")
            else:
                cfg["lyrics"]["parse_sections"] = bool(raw_ps)

        # 全屏设置
        if "fullscreen/context_lines" in keys:
            try:
                cfg["fullscreen"]["context_lines"] = int(s.value("fullscreen/context_lines"))
            except Exception:
                pass

        if "fullscreen/font_size_current" in keys:
            try:
                cfg["fullscreen"]["font_size_current"] = int(s.value("fullscreen/font_size_current"))
            except Exception:
                pass

        if "fullscreen/font_size_context" in keys:
            try:
                cfg["fullscreen"]["font_size_context"] = int(s.value("fullscreen/font_size_context"))
            except Exception:
                pass

        # 监听应用
        if "smtc/watched_apps" in keys:
            val = s.value("smtc/watched_apps")
            if isinstance(val, list):
                cfg["smtc"]["watched_apps"] = [str(v) for v in val if v]
            elif isinstance(val, str):
                cfg["smtc"]["watched_apps"] = [v.strip() for v in val.split(",") if v.strip()]

        # 运行模式
        if "window/mode" in keys:
            cfg["window"]["mode"] = str(s.value("window/mode"))

    except Exception as e:
        print(f"[Settings] 迁移 QSettings 失败: {e}")
    return cfg


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
                    _CACHE = _deep_merge(DEFAULT_CONFIG, data)
                else:
                    _CACHE = copy.deepcopy(DEFAULT_CONFIG)
            except Exception as e:
                print(f"[Settings] 读取 YAML 配置文件失败: {e}，将采用默认配置")
                _CACHE = copy.deepcopy(DEFAULT_CONFIG)
        else:
            # 首次运行，迁移 QSettings 并写出默认 config.yaml
            merged = _migrate_from_qsettings(copy.deepcopy(DEFAULT_CONFIG))
            _CACHE = merged
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
    return int(_get(["font", "size_current"], 28))

def get_font_size_context() -> int:
    return int(_get(["font", "size_context"], 14))

def get_fullscreen_context_lines() -> int:
    """全屏模式下当前歌词上下各显示的上下文行数（默认 5 行）"""
    return int(_get(["fullscreen", "context_lines"], 5))

def get_fullscreen_font_size_current() -> int:
    """全屏模式下当前行歌词字号（默认 38）"""
    val = _get(["fullscreen", "font_size_current"], None)
    if val is None:
        val = _get(["fullscreen", "size_current"], None)
    if val is None:
        return 38
    return int(val)

def get_fullscreen_font_size_context() -> int:
    """全屏模式下上下文歌词字号（默认 18）"""
    val = _get(["fullscreen", "font_size_context"], None)
    if val is None:
        val = _get(["fullscreen", "size_context"], None)
    if val is None:
        return 18
    return int(val)

def get_show_translation() -> bool:
    return bool(_get(["lyrics", "show_translation"], True))

def get_show_romaji() -> bool:
    return bool(_get(["lyrics", "show_romaji"], False))

def get_secondary_mode() -> str:
    """副行显示偏好：'prefer_trans' (优先译文), 'prefer_romaji' (优先罗马音), 'both' (并排显示)"""
    return str(_get(["lyrics", "secondary_mode"], "prefer_trans"))

def get_show_line_progress() -> bool:
    """无逐字歌词时是否在当前行下方显示单句进度条"""
    return bool(_get(["lyrics", "show_line_progress"], True))

def get_parse_sections() -> bool:
    """是否开启段落解析（隐藏章节与角色标记行，将角色名提取至翻译行）"""
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
    """生成标准化且易读的歌曲键名（例如：'晴天 - 周杰伦'）"""
    t = str(title or "").strip()
    a = str(artist or "").strip()
    return f"{t} - {a}" if a else t

def get_song_offsets() -> dict[str, int]:
    """读取所有单独配置的歌曲偏移字典（从 SQLite 数据库获取）"""
    try:
        from core import db_cache
        return db_cache.get_all_song_offsets()
    except Exception:
        return {}

def get_song_offset(title: str, artist: str = "") -> Optional[int]:
    """获取指定歌曲的单独偏移量（毫秒，从 SQLite 数据库获取），未单独配置时返回 None"""
    if not title:
        return None
    try:
        from core import db_cache
        return db_cache.get_song_offset(title, artist)
    except Exception:
        return None

def get_effective_song_offset(title: str, artist: str = "") -> int:
    """获取指定歌曲的最终生效偏移量（优先 SQLite 数据库独立配置，未配置时使用全局默认偏移）"""
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
