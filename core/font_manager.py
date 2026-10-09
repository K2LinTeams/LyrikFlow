"""
font_manager.py — 字体扫描、优先级排序与 Fallback 管理
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from typing import Optional
from PyQt6.QtGui import QFont, QFontDatabase, QFontMetrics

try:
    from core import settings
except ImportError:
    import settings


# ── 默认回退字体族 ───────────────────────────────────────────
SYSTEM_FALLBACK_FAMILIES = [
    "Comfortaa",
    "YouYuan",
    "幼圆",
    "Noto Sans SC",
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "Segoe UI",
    "PingFang SC",
    "sans-serif",
]


@dataclass
class FontItem:
    family: str                      # 字体家族名，如 "Zen Maru Gothic"
    files: list[str] = field(default_factory=list)  # 文件名列表
    paths: list[str] = field(default_factory=list)  # 文件绝对路径
    total_size: int = 0              # 字节总大小
    enabled: bool = True             # 是否启用
    is_valid: bool = True            # 文件是否存在且加载成功
    error_msg: str = ""              # 错误详情（如有）


_CACHED_ITEMS: list[FontItem] = []
_LOADED_PATHS: set[str] = set()
_FILE_TO_FAMILIES: dict[str, list[str]] = {}


def get_candidate_font_dirs() -> list[str]:
    """返回所有可能存放字体的有效目录列表（优先级：data/fonts -> 项目根/fonts -> 工作目录）"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base, "data", "fonts"),
        os.path.join(base, "fonts"),
        os.path.join(os.getcwd(), "data", "fonts"),
        os.path.join(os.getcwd(), "fonts"),
    ]
    seen = set()
    result = []
    for d in candidates:
        norm = os.path.normpath(d)
        if norm not in seen and os.path.isdir(norm):
            seen.add(norm)
            result.append(norm)
    return result


def get_fonts_dir() -> str:
    """获取主要字体目录绝对路径 (默认 data/fonts)"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.join(base, "data", "fonts")
    if not os.path.exists(target):
        try:
            os.makedirs(target, exist_ok=True)
        except Exception:
            pass
    return target


def format_bytes(size_bytes: int) -> str:
    """人性化格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def scan_fonts() -> list[FontItem]:
    """
    自动扫描 data/fonts (及兼容目录) 下的所有字体文件，载入 QFontDatabase，
    并与已保存的偏好设置（启用状态与优先级次序）进行合并对齐。
    """
    global _CACHED_ITEMS, _LOADED_PATHS, _FILE_TO_FAMILIES
    candidate_dirs = get_candidate_font_dirs()
    if not candidate_dirs:
        candidate_dirs = [get_fonts_dir()]

    # 收集磁盘上的字体文件 (文件名小写去重，以高优先级目录为准)
    found_files: dict[str, str] = {}  # fname_lower -> fpath
    for d in candidate_dirs:
        try:
            for fname in os.listdir(d):
                if fname.lower().endswith((".ttf", ".otf", ".ttc")):
                    key = fname.lower()
                    if key not in found_files:
                        found_files[key] = os.path.join(d, fname)
        except Exception:
            pass

    # 临时映射：family -> FontItem
    family_map: dict[str, FontItem] = {}

    for fname_lower, fpath in found_files.items():
        fname = os.path.basename(fpath)
        file_size = 0
        try:
            file_size = os.path.getsize(fpath)
        except Exception:
            pass

        fid = -1
        try:
            fid = QFontDatabase.addApplicationFont(fpath)
            _LOADED_PATHS.add(fpath)
        except Exception as e:
            print(f"[FontManager] 注册字体文件异常 {fname}: {e}")

        fams: list[str] = []
        if fid >= 0:
            fams = QFontDatabase.applicationFontFamilies(fid)
            if fams:
                _FILE_TO_FAMILIES[fpath] = fams
        elif fpath in _FILE_TO_FAMILIES:
            # 之前已成功注册过该文件，直接复用已缓存的族名
            fams = _FILE_TO_FAMILIES[fpath]

        if fid < 0 and not fams:
            # 字体加载失败
            base_name = os.path.splitext(fname)[0]
            if base_name not in family_map:
                family_map[base_name] = FontItem(
                    family=base_name,
                    files=[fname],
                    paths=[fpath],
                    total_size=file_size,
                    enabled=False,
                    is_valid=False,
                    error_msg="无法解析或不受支持的字体格式",
                )
            else:
                item = family_map[base_name]
                item.files.append(fname)
                item.paths.append(fpath)
                item.total_size += file_size
                item.is_valid = False
                item.error_msg = "部分字体文件解析失败"
            continue

        primary_family = fams[0] if fams else os.path.splitext(fname)[0]

        if primary_family not in family_map:
            family_map[primary_family] = FontItem(
                family=primary_family,
                files=[fname],
                paths=[fpath],
                total_size=file_size,
                enabled=True,
                is_valid=True,
                error_msg="",
            )
        else:
            item = family_map[primary_family]
            if fname not in item.files:
                item.files.append(fname)
                item.paths.append(fpath)
                item.total_size += file_size

    # 读取保存的优先级与启用状态进行合并
    saved_configs = settings.get_font_configs()
    ordered_items: list[FontItem] = []
    processed_families: set[str] = set()

    # 匹配字体项（支持精确匹配、忽略大小写匹配与文件名匹配）
    def find_item_for_family(target_name: str) -> Optional[FontItem]:
        if target_name in family_map:
            return family_map[target_name]
        t_lower = target_name.strip().lower()
        for k, v in family_map.items():
            if k.strip().lower() == t_lower:
                return v
            for fn in v.files:
                base = os.path.splitext(fn)[0].strip().lower()
                if base == t_lower:
                    return v
        return None

    # 1. 优先按已保存配置排序
    for conf in saved_configs:
        fam = conf.get("family", "")
        if not fam:
            continue
        enabled = conf.get("enabled", True)
        matched = find_item_for_family(fam)
        if matched:
            matched.enabled = bool(enabled)
            if matched.family not in processed_families:
                ordered_items.append(matched)
                processed_families.add(matched.family)
        else:
            # 记录配置中存在但本地缺失的字体项
            ordered_items.append(
                FontItem(
                    family=fam,
                    files=[],
                    paths=[],
                    total_size=0,
                    enabled=bool(enabled),
                    is_valid=False,
                    error_msg="本地字体文件缺失",
                )
            )
            processed_families.add(fam)

    # 2. 追加新扫描到但未配置过的字体
    for fam, item in family_map.items():
        if fam not in processed_families:
            ordered_items.append(item)

    _CACHED_ITEMS = ordered_items
    return _CACHED_ITEMS


def get_font_items() -> list[FontItem]:
    """获取当前字体列表（未扫描则自动扫描）"""
    global _CACHED_ITEMS
    if not _CACHED_ITEMS:
        return scan_fonts()
    return _CACHED_ITEMS


def save_font_items(items: list[FontItem]) -> None:
    """持久化字体优先级次序与启用配置"""
    global _CACHED_ITEMS
    _CACHED_ITEMS = list(items)
    data = [{"family": it.family, "enabled": it.enabled} for it in items]
    settings.set_font_configs(data)


def get_effective_font_families() -> list[str]:
    """
    获取生效的字体族名回退列表：
    已启用的有效本地字体 + 默认回退字体栈。
    """
    items = get_font_items()
    active_local: list[str] = [
        it.family for it in items if it.enabled and it.is_valid
    ]

    combined = active_local + SYSTEM_FALLBACK_FAMILIES
    result: list[str] = []
    seen: set[str] = set()
    for fam in combined:
        if fam and fam not in seen:
            seen.add(fam)
            result.append(fam)
    return result


def get_font_css_family(custom_items: Optional[list[FontItem]] = None) -> str:
    """
    计算适合用于 QSS / CSS 样式表的 font-family 字符串。
    若提供了 custom_items（如设置面板内存中暂存的字体排序列表），则基于该列表计算；
    否则基于全局生效列表计算。
    """
    if custom_items is not None:
        active_local = [it.family for it in custom_items if it.enabled and it.is_valid]
        combined = active_local + SYSTEM_FALLBACK_FAMILIES
        fams: list[str] = []
        seen: set[str] = set()
        for f in combined:
            if f and f not in seen:
                seen.add(f)
                fams.append(f)
    else:
        fams = get_effective_font_families()
    return ", ".join(f'"{fam}"' for fam in fams)


def make_app_font(
    size: int,
    bold: bool = False,
    weight: Optional[QFont.Weight] = None,
    families: Optional[list[str]] = None,
) -> QFont:
    """构建 QFont 并应用生效的字体回退栈"""
    f = QFont()
    f.setFamilies(families if families is not None else get_effective_font_families())
    f.setPointSize(size)
    if weight is not None:
        f.setWeight(weight)
    else:
        f.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Medium)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f


def open_fonts_folder() -> None:
    """在文件资源管理器中打开 fonts 文件夹，方便用户拖入字体"""
    fdir = get_fonts_dir()
    try:
        if os.name == "nt":
            os.startfile(fdir)
        else:
            subprocess.Popen(["xdg-open", fdir])
    except Exception as e:
        print(f"[FontManager] 打开文件夹失败: {e}")


def get_font_sample_text(family: str) -> str:
    """
    根据字体自身实际支持的文字系统与字形集合，生成能够 100% 由该字体独立渲染的预览样例文本。
    禁止依赖任何跨字体回退，确保每个字体的预览卡片只展示该字体自身的真实效果。
    """
    ws = set(w.name for w in QFontDatabase.writingSystems(family))
    has_simplified = "SimplifiedChinese" in ws
    has_traditional = "TraditionalChinese" in ws
    has_japanese = "Japanese" in ws

    f = QFont(family, 13)
    f.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
    fm = QFontMetrics(f)

    # 优先级候选样本文本（按完整字形覆盖率测试）
    candidates: list[str] = [
        "风吹过海面的声音，像是一首未完成的歌 1234 ABC",
        "不可解で不完全な魔法 · 風が海を渡る音 1234 ABC",
        "不可解的、不完全的魔法 1234 ABC",
        "The quick brown fox jumps over the lazy dog 1234 ABC",
    ]

    for text in candidates:
        if all(fm.inFont(c) for c in text):
            return text

    base_chars = "风吹过海面的声音不可解で不完全な魔法 The quick brown fox jumps 1234567890 ABC"
    supported = [c for c in base_chars if fm.inFont(c)]
    if len(supported) >= 8:
        return "".join(supported[:30])

    return "The quick brown fox jumps over the lazy dog 1234 ABC"

