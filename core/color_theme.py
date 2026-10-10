"""
color_theme.py — 色彩生成与配色管理
"""
from __future__ import annotations

import math
from typing import Any


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    elif len(s) == 8:
        # 兼容带 alpha 通道的情况，截取前 6 位 RGB
        s = s[:6]
    elif len(s) != 6:
        return (255, 255, 255)
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return (255, 255, 255)


def rgb_to_hex(r: int | float, g: int | float, b: int | float) -> str:
    cr = max(0, min(255, int(round(r))))
    cg = max(0, min(255, int(round(g))))
    cb = max(0, min(255, int(round(b))))
    return f"#{cr:02X}{cg:02X}{cb:02X}"


def is_valid_hex(hex_str: str) -> bool:
    s = hex_str.strip().lstrip("#")
    if len(s) not in (3, 6, 8):
        return False
    return all(c in "0123456789abcdefABCDEF" for c in s)


def normalize_hex(hex_str: str, default: str = "#0B57D0") -> str:
    if not is_valid_hex(hex_str):
        return default
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    elif len(s) == 8:
        s = s[:6]
    return f"#{s.upper()}"


def rgb_to_xyz(r: float, g: float, b: float) -> tuple[float, float, float]:
    def inv_gamma(v: float) -> float:
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    lr, lg, lb = inv_gamma(r), inv_gamma(g), inv_gamma(b)
    x = lr * 0.4124564 + lg * 0.3575761 + lb * 0.1804375
    y = lr * 0.2126729 + lg * 0.7151522 + lb * 0.0721750
    z = lr * 0.0193339 + lg * 0.1191920 + lb * 0.9503041
    return x, y, z


def xyz_to_lab(x: float, y: float, z: float) -> tuple[float, float, float]:
    xn, yn, zn = 0.95047, 1.00000, 1.08883

    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0

    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    return L, a, b


def lab_to_lch(L: float, a: float, b: float) -> tuple[float, float, float]:
    C = math.sqrt(a * a + b * b)
    H = math.degrees(math.atan2(b, a)) % 360.0
    return L, C, H


def lch_to_lab(L: float, C: float, H: float) -> tuple[float, float, float]:
    rad = math.radians(H)
    return L, C * math.cos(rad), C * math.sin(rad)


def lab_to_xyz(L: float, a: float, b: float) -> tuple[float, float, float]:
    xn, yn, zn = 0.95047, 1.00000, 1.08883
    fy = (L + 16.0) / 116.0
    fx = a / 500.0 + fy
    fz = fy - b / 200.0

    def inv_f(t: float) -> float:
        return t ** 3 if t ** 3 > 0.008856 else (t - 16.0 / 116.0) / 7.787

    return inv_f(fx) * xn, inv_f(fy) * yn, inv_f(fz) * zn


def _xyz_to_rgb_linear(x: float, y: float, z: float) -> tuple[float, float, float]:
    lr = x * 3.2404542 + y * -1.5371385 + z * -0.4985314
    lg = x * -0.9692660 + y * 1.8760108 + z * 0.0415560
    lb = x * 0.0556434 + y * -0.2040259 + z * 1.0572252
    return lr, lg, lb


def _is_in_srgb_gamut(x: float, y: float, z: float) -> bool:
    lr, lg, lb = _xyz_to_rgb_linear(x, y, z)
    eps = 0.001
    return (-eps <= lr <= 1.0 + eps) and (-eps <= lg <= 1.0 + eps) and (-eps <= lb <= 1.0 + eps)


def lch_to_rgb(L: float, C: float, H: float) -> tuple[int, int, int]:
    if L <= 0.0:
        return 0, 0, 0
    if L >= 100.0:
        return 255, 255, 255

    # 1. 检查原始彩度是否已在 sRGB 色域内
    x, y, z = lab_to_xyz(*lch_to_lab(L, C, H))
    best_c = C
    if not _is_in_srgb_gamut(x, y, z):
        # 2. 否则通过二分查找寻找该色调与明度下最大可表达彩度
        c_low = 0.0
        c_high = C
        best_c = 0.0
        for _ in range(12):
            c_mid = (c_low + c_high) / 2.0
            x_test, y_test, z_test = lab_to_xyz(*lch_to_lab(L, c_mid, H))
            if _is_in_srgb_gamut(x_test, y_test, z_test):
                best_c = c_mid
                c_low = c_mid
            else:
                c_high = c_mid

    # 3. 最终转换
    x_final, y_final, z_final = lab_to_xyz(*lch_to_lab(L, best_c, H))
    lr, lg, lb = _xyz_to_rgb_linear(x_final, y_final, z_final)

    def gamma(v: float) -> float:
        v = max(0.0, min(1.0, v))
        return 12.92 * v if v <= 0.0031308 else 1.055 * (v ** (1.0 / 2.4)) - 0.055

    return (
        int(round(gamma(lr) * 255.0)),
        int(round(gamma(lg) * 255.0)),
        int(round(gamma(lb) * 255.0)),
    )

STANDARD_TONES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 100]


def generate_tonal_palette(H: float, C: float, tones: list[int] | None = None) -> dict[int, str]:
    if tones is None:
        tones = STANDARD_TONES
    res: dict[int, str] = {}
    for t in tones:
        r, g, b = lch_to_rgb(float(t), C, H)
        res[t] = rgb_to_hex(r, g, b)
    return res


def generate_md_color_scheme(seed_color: str | tuple[int, int, int]) -> dict[str, Any]:
    if isinstance(seed_color, str):
        seed_hex = normalize_hex(seed_color, "#0B57D0")
        r, g, b = hex_to_rgb(seed_hex)
    else:
        r, g, b = seed_color
        seed_hex = rgb_to_hex(r, g, b)

    # 提取种子颜色的感知感知参数
    L, C, H = lab_to_lch(*xyz_to_lab(*rgb_to_xyz(r, g, b)))

    primary_c = max(36.0, min(90.0, C))
    secondary_c = max(14.0, C * 0.35)
    tertiary_c = max(24.0, C * 0.65)
    tertiary_h = (H + 60.0) % 360.0
    neutral_c = min(8.0, max(2.0, C * 0.10))
    neutral_var_c = min(16.0, max(4.0, C * 0.20))
    error_h = 25.0
    error_c = 70.0

    # 生成各调色板色阶
    p_tonal = generate_tonal_palette(H, primary_c)
    s_tonal = generate_tonal_palette(H, secondary_c)
    t_tonal = generate_tonal_palette(tertiary_h, tertiary_c)
    n_tonal = generate_tonal_palette(H, neutral_c)
    nv_tonal = generate_tonal_palette(H, neutral_var_c)
    err_tonal = generate_tonal_palette(error_h, error_c)

    # MD3 亮色
    md3_light = {
        "primary": p_tonal[40],
        "on_primary": "#FFFFFF",
        "primary_container": p_tonal[90],
        "on_primary_container": p_tonal[10],
        "secondary": s_tonal[40],
        "on_secondary": "#FFFFFF",
        "secondary_container": s_tonal[90],
        "on_secondary_container": s_tonal[10],
        "tertiary": t_tonal[40],
        "on_tertiary": "#FFFFFF",
        "tertiary_container": t_tonal[90],
        "on_tertiary_container": t_tonal[10],
        "error": err_tonal[40],
        "on_error": "#FFFFFF",
        "error_container": err_tonal[90],
        "on_error_container": err_tonal[10],
        "background": n_tonal[98],
        "on_background": n_tonal[10],
        "surface": n_tonal[98],
        "on_surface": n_tonal[10],
        "surface_variant": nv_tonal[90],
        "on_surface_variant": nv_tonal[30],
        "outline": nv_tonal[50],
        "outline_variant": nv_tonal[80],
    }

    # MD3 暗色
    md3_dark = {
        "primary": p_tonal[80],
        "on_primary": p_tonal[20],
        "primary_container": p_tonal[30],
        "on_primary_container": p_tonal[90],
        "secondary": s_tonal[80],
        "on_secondary": s_tonal[20],
        "secondary_container": s_tonal[30],
        "on_secondary_container": s_tonal[90],
        "tertiary": t_tonal[80],
        "on_tertiary": t_tonal[20],
        "tertiary_container": t_tonal[30],
        "on_tertiary_container": t_tonal[90],
        "error": err_tonal[80],
        "on_error": err_tonal[20],
        "error_container": err_tonal[30],
        "on_error_container": err_tonal[90],
        "background": n_tonal[10],
        "on_background": n_tonal[90],
        "surface": n_tonal[10],
        "on_surface": n_tonal[90],
        "surface_variant": nv_tonal[30],
        "on_surface_variant": nv_tonal[80],
        "outline": nv_tonal[60],
        "outline_variant": nv_tonal[30],
    }

    # LyrikFlow title
    lyrik_roles = {
        "lyric_active": p_tonal[95],
        "lyric_inactive": s_tonal[80],
        "lyric_secondary": t_tonal[80],
        "progress_start": p_tonal[90],
        "progress_end": t_tonal[70],
        "accent": p_tonal[70],
        "bg_tint": n_tonal[10],
    }

    return {
        "seed_color": seed_hex,
        "tonal_palettes": {
            "primary": p_tonal,
            "secondary": s_tonal,
            "tertiary": t_tonal,
            "neutral": n_tonal,
            "neutral_variant": nv_tonal,
            "error": err_tonal,
        },
        "md3_light": md3_light,
        "md3_dark": md3_dark,
        "lyrik_roles": lyrik_roles,
    }


# ── 预设配色方案 ─────────────────────────────────────────────────────────────

PRESET_THEMES: dict[str, dict[str, Any]] = {
    "classic": {
        "name": "湛蓝依旧🌠",
        "description": "LyrikFlow 默认",
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
    "sakura": {
        "name": "落樱粉雪🌸",
        "description": "洛可可",
        "seed_color": "#FFD8DF",
        "colors": {
            "lyric_active": "#E2BDC4",
            "lyric_inactive": "#FFECEF",
            "lyric_secondary": "#E7BF9E",
            "progress_start": "#FFD9E0",
            "progress_end": "#CAA484",
            "accent": "#EA92A5",
        },
    },
    "orange": {
        "name": "酸橙色信笺🍊",
        "description": "直到大地变成一颗酸橙",
        "seed_color": "#5B9CF5",
        "colors": {
            "lyric_active": "#7AAFE7",
            "lyric_inactive": "#F2EBF5",
            "lyric_secondary": "#F6A848",
            "progress_start": "#9ED1F9",
            "progress_end": "#CFD3F7",
            "accent": "#78ACFF",
        },
    },
    "custom": {
        "name": "自定义配色",
        "description": "自定义",
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


def get_preset(preset_key: str) -> dict[str, Any]:
    """获取指定预设，若不存在则回退至经典默认"""
    return PRESET_THEMES.get(preset_key, PRESET_THEMES["classic"])


def get_default_colors() -> dict[str, str]:
    """获取经典默认配色字典"""
    return dict(PRESET_THEMES["classic"]["colors"])
