"""
gui/lyric_scroll.py — 歌词平滑组件
"""
from __future__ import annotations

import math
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QColor, QPainter, QFontMetrics, QLinearGradient, QBrush, QImage,
)


class LyricScrollTracker:

    def __init__(self, damping: float = 0.15, golden_ratio: float = 0.42):
        self.scroll_x: float = 0.0
        self.target_scroll_x: float = 0.0
        self.damping: float = damping
        self.golden_ratio: float = golden_ratio

    def reset(self) -> None:
        self.scroll_x = 0.0
        self.target_scroll_x = 0.0

    def tick(self) -> bool:
        diff = self.target_scroll_x - self.scroll_x
        if abs(diff) > 0.01:
            self.scroll_x += diff * self.damping
            return True
        else:
            self.scroll_x = self.target_scroll_x
            return False

    def update_target(
        self,
        main_w: float,
        view_w: float,
        focus_offset: float,
    ) -> tuple[float, float]:
        if main_w <= view_w:
            self.target_scroll_x = 0.0
            return 0.0, 0.0

        max_scroll = main_w - view_w
        target_shift = focus_offset - (view_w * self.golden_ratio)
        if target_shift <= 0.0:
            self.target_scroll_x = 0.0
            return 0.0, max_scroll

        r = min(180.0, max(20.0, max_scroll * 0.4))
        if target_shift <= max_scroll - r:
            self.target_scroll_x = target_shift
        elif target_shift >= max_scroll + r:
            self.target_scroll_x = max_scroll
        else:
            t = (max_scroll - target_shift) / r
            self.target_scroll_x = max_scroll - (r / 4.0) * ((t + 1.0) ** 2)

        self.target_scroll_x = max(0.0, min(max_scroll, self.target_scroll_x))
        return self.target_scroll_x, max_scroll


def compute_focus_offset(
    words: Optional[list],
    main_text: str,
    line_time_ms: int,
    line_dur_ms: int,
    live_ms: float,
    fm: QFontMetrics,
    is_verbatim: bool = True,
    word_widths: Optional[list[float]] = None,
) -> float:
    if is_verbatim and words:
        curr_w_x = 0.0
        for i, wd in enumerate(words):
            wd_w = word_widths[i] if (word_widths is not None and i < len(word_widths)) else float(fm.horizontalAdvance(wd.text))
            w_start = wd.time_ms
            w_dur = max(1, wd.duration_ms)
            w_end = w_start + w_dur
            if live_ms >= w_end:
                curr_w_x += wd_w
            elif live_ms >= w_start:
                r = min(1.0, max(0.0, (live_ms - w_start) / float(w_dur)))
                curr_w_x += wd_w * r
                break
            else:
                break
        return curr_w_x
    else:
        main_w = float(fm.horizontalAdvance(main_text))
        dur = max(1000, line_dur_ms)
        r = min(1.0, max(0.0, (live_ms - line_time_ms) / float(dur)))
        return main_w * r


def compute_secondary_x(
    sub_text: str,
    fm_sub: QFontMetrics,
    w: int,
    view_w: float,
    side_margin: float,
    max_scroll: float,
    scroll_x: float,
    sub_w: Optional[float] = None,
) -> float:
    if sub_w is None:
        sub_w = float(fm_sub.horizontalAdvance(sub_text))
    if sub_w > view_w:
        sub_max = sub_w - view_w
        scroll_ratio = (scroll_x / max_scroll) if max_scroll > 0.001 else 0.0
        sub_scroll = sub_max * scroll_ratio
        return side_margin - sub_scroll
    else:
        return (w - sub_w) / 2.0


def apply_edge_feather_mask(
    painter: QPainter,
    width: int,
    height: int,
    fade_margin: float,
) -> None:
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    mask_grad = QLinearGradient(0, 0, width, 0)
    p_left = min(0.35, fade_margin / float(width))
    p_right = max(0.65, (float(width) - fade_margin) / float(width))
    mask_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
    mask_grad.setColorAt(p_left, QColor(0, 0, 0, 255))
    mask_grad.setColorAt(p_right, QColor(0, 0, 0, 255))
    mask_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
    painter.fillRect(0, 0, width, height, QBrush(mask_grad))


class LayerBufferCache:

    def __init__(self):
        self._buffer: Optional[QImage] = None

    def get(self, width: int, height: int, dpr: float) -> QImage:
        pw = int(math.ceil(width * dpr))
        ph = int(math.ceil(height * dpr))
        if (self._buffer is None
                or self._buffer.width() != pw
                or self._buffer.height() != ph):
            self._buffer = QImage(pw, ph, QImage.Format.Format_ARGB32_Premultiplied)
            self._buffer.setDevicePixelRatio(dpr)
        self._buffer.fill(Qt.GlobalColor.transparent)
        return self._buffer

    def invalidate(self) -> None:
        self._buffer = None
