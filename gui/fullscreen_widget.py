"""
fullscreen_widget.py — 全屏歌词视图组件
"""
from __future__ import annotations

import time
import math
from typing import Optional

from PyQt6.QtCore import (
    Qt, QTimer, QRectF, QPointF,
)
from PyQt6.QtGui import (
    QColor, QPainter, QFont, QFontMetrics, QPixmap,
    QLinearGradient, QRadialGradient, QPainterPath,
    QKeyEvent, QImage, QPen, QBrush,
)
from PyQt6.QtWidgets import (
    QWidget, QApplication, QVBoxLayout, QMenu,
    QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene,
)

try:
    from core import settings, font_manager
    from core.lyrics_parser import ParsedLyrics
except ImportError:
    import settings
    import font_manager
    from lyrics_parser import ParsedLyrics

try:
    from gui.lyric_scroll import (
        LyricScrollTracker, compute_focus_offset,
        compute_secondary_x, apply_edge_feather_mask, LayerBufferCache,
    )
except ImportError:
    from lyric_scroll import (
        LyricScrollTracker, compute_focus_offset,
        compute_secondary_x, apply_edge_feather_mask, LayerBufferCache,
    )


# ── 颜色常量 ─────────────────────────────────────────────────────────────────
COLOR_CUR       = QColor(255, 255, 255, 255)
COLOR_NEXT      = QColor(255, 255, 255, 175)
COLOR_FAR       = QColor(255, 255, 255, 80)
COLOR_TRANS_CUR = QColor(195, 225, 255, 215)
COLOR_TRANS_CTX = QColor(195, 225, 255, 95)
HORIZ_FADE_MARGIN  = 96.0   # 左右两端虚化渐变遮罩宽度
HORIZ_SIDE_PADDING = 80.0   # 视口安全边距


def _make_font(size: int, bold: bool = False) -> QFont:
    return font_manager.make_app_font(size, bold=bold)


# ── 歌词滚动画布 ──────────────────────────────────────────────────────────────
class LyricsCanvas(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lyrics: Optional[ParsedLyrics] = None
        self._cur_index: int = -1
        self._base_ms: float = 0.0
        self._base_wall_time: float = time.monotonic()
        self._is_playing: bool = True
        self._is_verbatim_song: bool = False
        self._scroll_offset: float = 0.0      # 当前绘制偏移
        self._target_offset: float = 0.0
        self._scroll_tracker = LyricScrollTracker(damping=0.10, golden_ratio=0.42)
        self._line_cache = LayerBufferCache()
        self._show_translation = settings.get_show_translation()
        self._show_romaji = settings.get_show_romaji()
        self._context_secondary_mode = settings.get_fullscreen_context_secondary_mode()
        self._parse_sections = settings.get_parse_sections()
        self._context_lines = settings.get_fullscreen_context_lines()

        cur_sz = settings.get_fullscreen_font_size_current()
        ctx_sz = settings.get_fullscreen_font_size_context()
        self._font_cur        = _make_font(cur_sz, bold=True)
        self._font_near       = _make_font(ctx_sz, bold=False)
        self._font_far        = _make_font(max(10, ctx_sz - 4), bold=False)
        self._font_trans_cur  = _make_font(max(12, int(cur_sz * 0.6)), bold=False)
        self._font_trans_ctx  = _make_font(max(10, int(ctx_sz * 0.8)), bold=False)

        # 缓存字体度量，避免每帧重复构造 QFontMetrics
        self._fm_cur = QFontMetrics(self._font_cur)
        self._fm_near = QFontMetrics(self._font_near)
        self._fm_far = QFontMetrics(self._font_far)
        self._fm_trans_cur = QFontMetrics(self._font_trans_cur)
        self._fm_trans_ctx = QFontMetrics(self._font_trans_ctx)

        # 主题色彩方案
        self._load_theme_colors()

        # 60FPS 连续渲染与缓动滚动驱动计时器
        self._anim_timer = QTimer(self)
        self._anim_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._anim_timer.setInterval(16)  # ~60fps
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_timer.start()

        self.setMinimumHeight(400)

    def _load_theme_colors(self):
        self._color_act = QColor(settings.get_theme_color("lyric_active", "#FFFFFF"))
        self._color_inact = QColor(settings.get_theme_color("lyric_inactive", "#A0A8B8"))
        self._color_sec = QColor(settings.get_theme_color("lyric_secondary", "#C3E1FF"))
        self._color_prog_start = QColor(settings.get_theme_color("progress_start", "#FFFFFF"))
        self._color_prog_end = QColor(settings.get_theme_color("progress_end", "#A0E6FF"))
        self._color_accent = QColor(settings.get_theme_color("accent", "#78CDFF"))

    def reload_settings(self):
        self._load_theme_colors()
        self._show_translation = settings.get_show_translation()
        self._show_romaji = settings.get_show_romaji()
        self._context_secondary_mode = settings.get_fullscreen_context_secondary_mode()
        self._parse_sections = settings.get_parse_sections()
        self._context_lines = settings.get_fullscreen_context_lines()
        cur_sz = settings.get_fullscreen_font_size_current()
        ctx_sz = settings.get_fullscreen_font_size_context()
        self._font_cur        = _make_font(cur_sz, bold=True)
        self._font_near       = _make_font(ctx_sz, bold=False)
        self._font_far        = _make_font(max(10, ctx_sz - 4), bold=False)
        self._font_trans_cur  = _make_font(max(12, int(cur_sz * 0.6)), bold=False)
        self._font_trans_ctx  = _make_font(max(10, int(ctx_sz * 0.8)), bold=False)
        self._fm_cur = QFontMetrics(self._font_cur)
        self._fm_near = QFontMetrics(self._font_near)
        self._fm_far = QFontMetrics(self._font_far)
        self._fm_trans_cur = QFontMetrics(self._font_trans_cur)
        self._fm_trans_ctx = QFontMetrics(self._font_trans_ctx)
        self._line_cache.invalidate()
        if self._cur_index >= 0:
            self._target_offset = self._calc_offset_for(self._cur_index)
        self.update()

    def _get_live_elapsed_ms(self) -> float:
        if not self._is_playing:
            return self._base_ms
        delta = (time.monotonic() - self._base_wall_time) * 1000.0
        return self._base_ms + max(0.0, delta)

    def _on_anim_tick(self):
        diff = self._target_offset - self._scroll_offset
        is_moving = abs(diff) > 0.2
        if is_moving:
            self._scroll_offset += diff * 0.12   # 平滑缓动插值
        else:
            self._scroll_offset = self._target_offset

        # 超长单句横向平滑相机跟随插值
        is_h_moving = self._scroll_tracker.tick()

        if self._is_playing or is_moving or is_h_moving:
            self.update()

    def set_lyrics(self, lyrics: Optional[ParsedLyrics]):
        self._lyrics = lyrics
        # 切歌时统一判定整首歌是否具备逐字数据
        self._is_verbatim_song = bool(
            lyrics and any(bool(line.words) for line in lyrics.lines)
        )
        self._cur_index = -1
        self._target_offset = self._calc_offset_for(0)
        self._scroll_offset = self._target_offset
        self._scroll_tracker.reset()
        self._line_cache.invalidate()
        self.update()

    def set_current_time(self, elapsed_ms: int, idx: int):
        self._base_ms = float(elapsed_ms)
        self._base_wall_time = time.monotonic()
        if idx != self._cur_index:
            prev_idx = self._cur_index
            self._cur_index = idx
            self._target_offset = self._calc_offset_for(idx)
            self._scroll_tracker.reset()
            if prev_idx < 0:
                self._scroll_offset = self._target_offset
        self.update()

    def set_current_index(self, idx: int):
        if idx == self._cur_index:
            return
        prev_idx = self._cur_index
        self._cur_index = idx
        self._target_offset = self._calc_offset_for(idx)
        self._scroll_tracker.reset()
        if prev_idx < 0:
            self._scroll_offset = self._target_offset
        self.update()

    def set_playing(self, playing: bool):
        if self._is_playing and not playing:
            self._base_ms = self._get_live_elapsed_ms()
        self._is_playing = playing
        self._base_wall_time = time.monotonic()
        self.update()

    def set_show_translation(self, v: bool):
        self._show_translation = v
        self._target_offset = self._calc_offset_for(self._cur_index)
        self.update()

    def set_show_romaji(self, v: bool):
        self._show_romaji = v
        self._target_offset = self._calc_offset_for(self._cur_index)
        self.update()

    def set_context_secondary_mode(self, v: str):
        if v not in ("none", "translation", "romaji", "both"):
            v = "both"
        self._context_secondary_mode = v
        self._target_offset = self._calc_offset_for(self._cur_index)
        self.update()

    def set_parse_sections(self, v: bool):
        self._parse_sections = v
        self._target_offset = self._calc_offset_for(self._cur_index)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._cur_index >= 0:
            self._target_offset = self._calc_offset_for(self._cur_index)

    def _get_line_flags(self, line, dist: int) -> tuple[bool, bool, bool]:
        if dist == 0:
            has_ro = bool(self._show_romaji and line.romaji.strip())
            has_tr = bool(self._show_translation and line.translation.strip())
            has_sec = bool(self._parse_sections and (line.section or line.role))
        else:
            mode = self._context_secondary_mode
            if mode == "none":
                has_ro = False
                has_tr = False
                has_sec = False
            elif mode == "translation":
                has_ro = False
                has_tr = bool(self._show_translation and line.translation.strip())
                has_sec = bool(self._parse_sections and (line.section or line.role))
            elif mode == "romaji":
                has_ro = bool(self._show_romaji and line.romaji.strip())
                has_tr = False
                has_sec = bool(self._parse_sections and (line.section or line.role))
            else:  # "both"
                has_ro = bool(self._show_romaji and line.romaji.strip())
                has_tr = bool(self._show_translation and line.translation.strip())
                has_sec = bool(self._parse_sections and (line.section or line.role))
        return has_ro, has_tr, has_sec

    def _calc_offset_for(self, idx: int) -> float:
        if not self._lyrics or not self._lyrics.lines:
            return 0.0
        target_idx = max(0, min(len(self._lyrics.lines) - 1, idx if idx >= 0 else 0))
        y = 0.0
        for i, line in enumerate(self._lyrics.lines):
            _, _, has_t = self._line_meta(i, target_idx)
            lh = self._line_height(i, target_idx, has_t)
            if i == target_idx:
                has_ro, has_tr, has_sec = self._get_line_flags(line, 0)
                text_h = float(self._fm_cur.height())
                sub_h = float(self._fm_trans_cur.height() + 6)
                if has_ro:
                    text_h += sub_h
                if has_tr:
                    text_h += sub_h
                if not (has_ro or has_tr) and has_sec:
                    sec = line.get_secondary_text(False, False, parse_sections=True)
                    if sec:
                        text_h += sub_h
                line_mid = y + text_h / 2.0
                viewport_h = float(self.height()) if self.height() > 50 else 800.0
                target_center_y = viewport_h * 0.48
                return line_mid - target_center_y
            y += lh
        return 0.0

    def _line_meta(self, i: int, cur: int) -> tuple[QFont, QFontMetrics, bool]:
        dist = abs(i - cur)
        if dist == 0:
            fnt = self._font_cur
            fm = self._fm_cur
        elif dist == 1:
            fnt = self._font_near
            fm = self._fm_near
        else:
            fnt = self._font_far
            fm = self._fm_far
        line = self._lyrics.lines[i]
        has_ro, has_tr, has_sec = self._get_line_flags(line, dist)
        has_t = has_ro or has_tr or has_sec
        return fnt, fm, has_t

    def _line_height(self, i: int, cur: int, has_t: bool) -> float:
        dist = abs(i - cur)
        if dist == 0:
            base = float(self._fm_cur.height())
            sub_h = float(self._fm_trans_cur.height() + 6)
        elif dist == 1:
            base = float(self._fm_near.height())
            sub_h = float(self._fm_trans_ctx.height() + 6)
        else:
            base = float(self._fm_far.height())
            sub_h = float(self._fm_trans_ctx.height() + 6)

        line = self._lyrics.lines[i]
        has_ro, has_tr, has_sec = self._get_line_flags(line, dist)

        if has_ro:
            base += sub_h
        if has_tr:
            base += sub_h
        if not (has_ro or has_tr) and has_sec:
            sec_text = line.get_secondary_text(False, False, parse_sections=True)
            if sec_text:
                base += sub_h

        return base + 24   # 行间距

    def _draw_current_active_line(
        self,
        p: QPainter,
        w: int,
        draw_y: float,
        fm: QFontMetrics,
        tfm: QFontMetrics,
        line,
        live_ms: float,
        final_alpha: int,
        fade_factor: float,
        start_x: float,
        main_w: float,
        view_w: float,
        max_scroll: float,
        word_widths: Optional[list[float]] = None,
        ro_w: float = 0.0,
        tr_w: float = 0.0,
    ) -> None:
        p.setFont(self._font_cur)
        main_text = line.text.strip()
        c_act = self._color_act
        c_inact = self._color_inact
        c_sec = self._color_sec

        # ── 1. 主行歌词绘制 ──
        if self._is_verbatim_song:
            if line.words:
                curr_x = start_x
                for idx, wd in enumerate(line.words):
                    ww = word_widths[idx] if (word_widths is not None and idx < len(word_widths)) else float(fm.horizontalAdvance(wd.text))
                    w_start = wd.time_ms
                    w_dur = max(1, wd.duration_ms)
                    w_end = w_start + w_dur

                    if live_ms < w_start:
                        p.setPen(QColor(c_inact.red(), c_inact.green(), c_inact.blue(), final_alpha))
                        p.drawText(QPointF(curr_x, draw_y + fm.ascent()), wd.text)
                    elif live_ms >= w_end:
                        p.setPen(QColor(c_act.red(), c_act.green(), c_act.blue(), final_alpha))
                        p.drawText(QPointF(curr_x, draw_y + fm.ascent()), wd.text)
                    else:
                        progress = min(1.0, max(0.0, (live_ms - w_start) / float(w_dur)))
                        wipe = QLinearGradient(curr_x, 0, curr_x + ww, 0)
                        col_full = QColor(c_act.red(), c_act.green(), c_act.blue(), final_alpha)
                        col_fade = QColor(c_inact.red(), c_inact.green(), c_inact.blue(), final_alpha)
                        wipe.setColorAt(0.0, col_full)
                        wipe.setColorAt(progress, col_full)
                        wipe.setColorAt(min(1.0, progress + 0.08), col_fade)
                        wipe.setColorAt(1.0, col_fade)
                        p.setPen(QPen(QBrush(wipe), 0))
                        p.drawText(QPointF(curr_x, draw_y + fm.ascent()), wd.text)
                    curr_x += ww
            else:
                curr_x = start_x
                dur = max(1000, line.duration_ms)
                progress = min(1.0, max(0.0, (live_ms - line.time_ms) / float(dur)))
                wipe = QLinearGradient(curr_x, 0, curr_x + main_w, 0)
                col_full = QColor(c_act.red(), c_act.green(), c_act.blue(), final_alpha)
                col_fade = QColor(c_inact.red(), c_inact.green(), c_inact.blue(), final_alpha)
                wipe.setColorAt(0.0, col_full)
                wipe.setColorAt(progress, col_full)
                wipe.setColorAt(min(1.0, progress + 0.08), col_fade)
                wipe.setColorAt(1.0, col_fade)
                p.setPen(QPen(QBrush(wipe), 0))
                p.drawText(QPointF(curr_x, draw_y + fm.ascent()), main_text)
        else:
            p.setPen(QColor(c_act.red(), c_act.green(), c_act.blue(), final_alpha))
            p.drawText(QPointF(start_x, draw_y + fm.ascent()), main_text)

        # ── 2. 副行（罗马音 / 译文 / 声部）绘制 ──
        has_ro, has_tr, has_sec = self._get_line_flags(line, 0)
        p.setFont(self._font_trans_cur)
        sub_y = draw_y + fm.height() + 8

        if has_ro:
            ro_text = line.romaji.strip()
            ttx = compute_secondary_x(
                sub_text=ro_text,
                fm_sub=tfm,
                w=w,
                view_w=view_w,
                side_margin=HORIZ_SIDE_PADDING,
                max_scroll=max_scroll,
                scroll_x=self._scroll_tracker.scroll_x,
                sub_w=ro_w,
            )
            ro_alpha = int(200 * fade_factor)
            if ro_alpha > 2:
                p.setPen(QColor(c_sec.red(), c_sec.green(), c_sec.blue(), ro_alpha))
                p.drawText(QPointF(ttx, sub_y + tfm.ascent()), ro_text)
            sub_y += tfm.height() + 6

        if has_tr:
            tr_text = line.translation.strip()
            ttx = compute_secondary_x(
                sub_text=tr_text,
                fm_sub=tfm,
                w=w,
                view_w=view_w,
                side_margin=HORIZ_SIDE_PADDING,
                max_scroll=max_scroll,
                scroll_x=self._scroll_tracker.scroll_x,
                sub_w=tr_w,
            )
            t_alpha = int(215 * fade_factor)
            if t_alpha > 2:
                p.setPen(QColor(c_sec.red(), c_sec.green(), c_sec.blue(), t_alpha))
                p.drawText(QPointF(ttx, sub_y + tfm.ascent()), tr_text)
            sub_y += tfm.height() + 6

        if not (has_ro or has_tr) and has_sec:
            sec_text = line.get_secondary_text(False, False, parse_sections=True)
            if sec_text:
                ttx = compute_secondary_x(
                    sub_text=sec_text,
                    fm_sub=tfm,
                    w=w,
                    view_w=view_w,
                    side_margin=HORIZ_SIDE_PADDING,
                    max_scroll=max_scroll,
                    scroll_x=self._scroll_tracker.scroll_x,
                )
                sec_alpha = int(200 * fade_factor)
                if sec_alpha > 2:
                    p.setPen(QColor(c_sec.red(), c_sec.green(), c_sec.blue(), sec_alpha))
                    p.drawText(QPointF(ttx, sub_y + tfm.ascent()), sec_text)

    def paintEvent(self, event):
        if not self._lyrics or self._lyrics.is_instrumental:
            return

        w, h = self.width(), self.height()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        cur = self._cur_index
        live_ms = self._get_live_elapsed_ms()
        y = -self._scroll_offset

        lines = self._lyrics.lines

        for i, line in enumerate(lines):
            fnt, fm, has_t = self._line_meta(i, cur)
            lh = self._line_height(i, cur, has_t)

            # 剔除视口外不可见行
            if y + lh < 0:
                y += lh
                continue
            if y > self.height():
                break

            if not line.text.strip():
                y += lh
                continue

            dist = abs(i - cur)

            # ── 1. 距离基础不透明度 ──
            max_ctx = max(1, self._context_lines)
            if dist == 0:
                base_alpha = 255
            elif dist <= max_ctx:
                ratio = (max_ctx + 1 - dist) / float(max_ctx + 1)
                base_alpha = int(225 * (ratio ** 1.25))
            else:
                base_alpha = 0

            # ── 2. 视口边缘自然渐隐 ──
            line_mid = y + lh * 0.5
            fade_factor = 1.0
            if line_mid < 170.0:
                fade_factor = max(0.0, min(1.0, (line_mid - 60.0) / 110.0))
            elif line_mid > (h - 200.0):
                fade_factor = max(0.0, min(1.0, (h - 70.0 - line_mid) / 130.0))

            final_alpha = int(base_alpha * fade_factor)
            if final_alpha <= 2:
                y += lh
                continue

            # 主文本绘制
            painter.setFont(fnt)
            main_text = line.text.strip()
            c_inact = self._color_inact
            c_sec = self._color_sec

            if dist == 0:
                tfm = self._fm_trans_cur
                view_w = max(100.0, float(w) - HORIZ_SIDE_PADDING * 2.0)

                # 计算当前行总宽度与演唱焦点
                if self._is_verbatim_song and line.words:
                    word_widths = [float(fm.horizontalAdvance(wd.text)) for wd in line.words]
                    main_w = float(sum(word_widths))
                else:
                    word_widths = None
                    main_w = float(fm.horizontalAdvance(main_text))

                focus_offset = compute_focus_offset(
                    words=line.words,
                    main_text=main_text,
                    line_time_ms=line.time_ms,
                    line_dur_ms=line.duration_ms,
                    live_ms=live_ms,
                    fm=fm,
                    is_verbatim=self._is_verbatim_song,
                    word_widths=word_widths,
                )

                target_scroll, max_scroll = self._scroll_tracker.update_target(main_w, view_w, focus_offset)

                has_ro, has_tr, _ = self._get_line_flags(line, 0)
                sub_overflow = False
                ro_w = float(tfm.horizontalAdvance(line.romaji.strip())) if has_ro else 0.0
                tr_w = float(tfm.horizontalAdvance(line.translation.strip())) if has_tr else 0.0
                if has_ro and ro_w > view_w:
                    sub_overflow = True
                if has_tr and tr_w > view_w:
                    sub_overflow = True

                if main_w > view_w:
                    start_x = HORIZ_SIDE_PADDING - self._scroll_tracker.scroll_x
                    needs_feather = True
                else:
                    start_x = (w - main_w) / 2.0
                    needs_feather = sub_overflow or (self._scroll_tracker.scroll_x > 0.5)

                if needs_feather:
                    dpr = self.devicePixelRatioF()
                    line_w = int(w)
                    line_h = int(math.ceil(lh)) + 4
                    layer_img = self._line_cache.get(line_w, line_h, dpr)

                    lp = QPainter(layer_img)
                    lp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                    lp.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

                    self._draw_current_active_line(
                        lp, w, 0.0, fm, tfm, line, live_ms, final_alpha, fade_factor,
                        start_x, main_w, view_w, max_scroll,
                        word_widths=word_widths, ro_w=ro_w, tr_w=tr_w,
                    )

                    apply_edge_feather_mask(lp, line_w, line_h, HORIZ_FADE_MARGIN)
                    lp.end()

                    painter.drawImage(QPointF(0.0, y), layer_img)
                else:
                    self._draw_current_active_line(
                        painter, w, y, fm, tfm, line, live_ms, final_alpha, fade_factor,
                        start_x, main_w, view_w, max_scroll,
                        word_widths=word_widths, ro_w=ro_w, tr_w=tr_w,
                    )
            else:
                # ── 非当前行（上下文背景行）绘制 ──
                elided = fm.elidedText(main_text, Qt.TextElideMode.ElideRight, w - 80)
                tx = (w - fm.horizontalAdvance(elided)) / 2.0
                painter.setPen(QColor(c_inact.red(), c_inact.green(), c_inact.blue(), final_alpha))
                painter.drawText(QPointF(tx, y + fm.ascent()), elided)

                # ── 副行绘制 ──
                has_ro, has_tr, has_sec = self._get_line_flags(line, dist)
                tfnt = self._font_trans_ctx
                painter.setFont(tfnt)
                tfm = self._fm_trans_ctx
                sub_y = y + fm.height() + 8

                if has_ro:
                    ro_text = line.romaji.strip()
                    te = tfm.elidedText(ro_text, Qt.TextElideMode.ElideRight, w - 80)
                    ttx = (w - tfm.horizontalAdvance(te)) / 2.0
                    base_ro_alpha = 85
                    ro_alpha = int(base_ro_alpha * (base_alpha / 255.0) * fade_factor)
                    if ro_alpha > 2:
                        painter.setPen(QColor(c_sec.red(), c_sec.green(), c_sec.blue(), ro_alpha))
                        painter.drawText(QPointF(ttx, sub_y + tfm.ascent()), te)
                    sub_y += tfm.height() + 6

                if has_tr:
                    tr_text = line.translation.strip()
                    te = tfm.elidedText(tr_text, Qt.TextElideMode.ElideRight, w - 80)
                    ttx = (w - tfm.horizontalAdvance(te)) / 2.0
                    base_t_alpha = 95
                    t_alpha = int(base_t_alpha * (base_alpha / 255.0) * fade_factor)
                    if t_alpha > 2:
                        painter.setPen(QColor(c_sec.red(), c_sec.green(), c_sec.blue(), t_alpha))
                        painter.drawText(QPointF(ttx, sub_y + tfm.ascent()), te)
                    sub_y += tfm.height() + 6

                if not (has_ro or has_tr) and has_sec:
                    sec_text = line.get_secondary_text(False, False, parse_sections=True)
                    if sec_text:
                        te = tfm.elidedText(sec_text, Qt.TextElideMode.ElideRight, w - 80)
                        ttx = (w - tfm.horizontalAdvance(te)) / 2.0
                        base_sec_alpha = 90
                        sec_alpha = int(base_sec_alpha * (base_alpha / 255.0) * fade_factor)
                        if sec_alpha > 2:
                            painter.setPen(QColor(c_sec.red(), c_sec.green(), c_sec.blue(), sec_alpha))
                            painter.drawText(QPointF(ttx, sub_y + tfm.ascent()), te)

            y += lh


# ── 全画幅主窗口 ──────────────────────────────────────────────────────────────
class FullscreenWidget(QWidget):

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._thumb_pixmap: Optional[QPixmap] = None
        self._title: str  = ""
        self._artist: str = ""
        self._lyrics: Optional[ParsedLyrics] = None
        self._cur_index: int = -1
        self._is_playing: bool = False
        self._elapsed_ms: int = 0
        self._total_ms: int = 0
        self._load_theme_colors()

        # 环境光晕三点采样色彩
        self._ambient_col_center = QColor(165, 145, 160)
        self._ambient_col_left   = QColor(135, 110, 115)
        self._ambient_col_right  = QColor(90, 100, 130)

        # 高斯模糊背景图缓存系统
        self._curr_bg_pixmap: Optional[QPixmap] = None
        self._prev_bg_pixmap: Optional[QPixmap] = None
        self._bg_crossfade: float = 1.0

        # 封面图缩略图与平滑 Crossfade 替换
        self._thumb_pixmap: Optional[QPixmap] = None
        self._prev_thumb_pixmap: Optional[QPixmap] = None
        self._thumb_crossfade: float = 1.0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 歌词画布
        self._canvas = LyricsCanvas(self)

        # 封面加载动画状态
        self._loading_progress: float = 1.0
        self._target_loading_progress: float = 1.0
        self._loading_spinner_angle: float = 0.0
        self._cover_alpha: float = 1.0
        self._target_cover_alpha: float = 1.0

        self._fs_anim_timer = QTimer(self)
        self._fs_anim_timer.setInterval(16)
        self._fs_anim_timer.timeout.connect(self._on_fs_tick)
        self._fs_anim_timer.start()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    # ── 高斯模糊全屏背景生成 ─────────────────────────────────────────────────
    def _generate_blurred_bg(self, pixmap: Optional[QPixmap]) -> Optional[QPixmap]:
        if not pixmap or pixmap.isNull():
            return None

        w = max(100, self.width())
        h = max(60, self.height())
        aspect = w / float(h)
        base_h = 100
        base_w = max(100, int(base_h * aspect))
        pad = 28  # 边界扩展，消除高斯模糊边缘收缩/发黑

        total_w = base_w + pad * 2
        total_h = base_h + pad * 2

        # 1. 缩放封面填满并居中截取
        scaled = pixmap.scaled(
            total_w, total_h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        sx = max(0, (scaled.width() - total_w) // 2)
        sy = max(0, (scaled.height() - total_h) // 2)
        cropped = scaled.copy(sx, sy, total_w, total_h)

        # 2. 应用高质量 QGraphicsBlurEffect
        try:
            scene = QGraphicsScene()
            item = QGraphicsPixmapItem(cropped)
            blur = QGraphicsBlurEffect()
            blur.setBlurRadius(32.0)
            blur.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
            item.setGraphicsEffect(blur)
            scene.addItem(item)

            blurred_total = QPixmap(total_w, total_h)
            blurred_total.fill(QColor(16, 18, 24))
            bp = QPainter(blurred_total)
            bp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            bp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            scene.render(bp, QRectF(0, 0, total_w, total_h), QRectF(0, 0, total_w, total_h))
            bp.end()

            return blurred_total.copy(pad, pad, base_w, base_h)
        except Exception:
            return cropped.scaled(
                base_w, base_h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

    def _update_background(self, pixmap: Optional[QPixmap]) -> None:
        if pixmap and not pixmap.isNull():
            new_bg = self._generate_blurred_bg(pixmap)
            if new_bg:
                if self._curr_bg_pixmap and not self._curr_bg_pixmap.isNull():
                    self._prev_bg_pixmap = self._curr_bg_pixmap
                    self._bg_crossfade = 0.0
                else:
                    self._prev_bg_pixmap = None
                    self._bg_crossfade = 1.0
                self._curr_bg_pixmap = new_bg
            else:
                self._curr_bg_pixmap = None
                self._prev_bg_pixmap = None
        else:
            self._prev_bg_pixmap = None
            self._curr_bg_pixmap = None
            self._bg_crossfade = 1.0

    # ── 环境光晕色彩生成 ─────────────────────────────────────────────────────
    def _update_ambient_palette(self, thumb_pixmap: Optional[QPixmap]) -> None:
        if not thumb_pixmap or thumb_pixmap.isNull():
            self._ambient_col_center = QColor(165, 145, 160)
            self._ambient_col_left   = QColor(135, 110, 115)
            self._ambient_col_right  = QColor(90, 100, 130)
            return

        img = thumb_pixmap.toImage().scaled(
            24, 24,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        c_center = img.pixelColor(12, 12)
        c_left   = img.pixelColor(4, 12)
        c_right  = img.pixelColor(20, 12)

        def _soften(c: QColor, target_sat: int, target_val: int) -> QColor:
            h, s, v, _ = c.getHsv()
            if h < 0:
                h = 240
            s = min(target_sat, max(35, s))
            v = min(target_val, max(70, v))
            return QColor.fromHsv(h, s, v)

        self._ambient_col_center = _soften(c_center, 80, 160)
        self._ambient_col_left   = _soften(c_left, 100, 135)
        self._ambient_col_right  = _soften(c_right, 100, 125)

    # ── 公共接口 ─────────────────────────────────────────────────────────────
    def set_song(self, title: str, artist: str, thumb_bytes: bytes):
        self._title  = title.strip()
        self._artist = artist.strip()
        self._prev_thumb_pixmap = None
        self._thumb_crossfade = 1.0
        if thumb_bytes:
            img = QImage.fromData(bytes(thumb_bytes))
            if not img.isNull():
                self._thumb_pixmap = QPixmap.fromImage(img)
                self._cover_alpha = 1.0
                self._target_cover_alpha = 1.0
            else:
                self._thumb_pixmap = None
                self._cover_alpha = 0.0
                self._target_cover_alpha = 0.0
        else:
            self._thumb_pixmap = None
            self._cover_alpha = 0.0
            self._target_cover_alpha = 0.0

        self._update_background(self._thumb_pixmap)
        self._update_ambient_palette(self._thumb_pixmap)
        self.update()

    def update_hd_cover(self, hd_cover_bytes: bytes):
        if not hd_cover_bytes:
            return
        img = QImage.fromData(bytes(hd_cover_bytes))
        if img.isNull():
            return
        new_pixmap = QPixmap.fromImage(img)
        if self._thumb_pixmap and not self._thumb_pixmap.isNull():
            # 已有封面：平滑 Crossfade 替换
            self._prev_thumb_pixmap = self._thumb_pixmap
            self._thumb_crossfade = 0.0
            self._thumb_pixmap = new_pixmap
            self._cover_alpha = 1.0
            self._target_cover_alpha = 1.0
        else:
            self._prev_thumb_pixmap = None
            self._thumb_crossfade = 1.0
            self._thumb_pixmap = new_pixmap
            self._cover_alpha = 0.0
            self._target_cover_alpha = 1.0
        self._target_loading_progress = 1.0
        self._update_background(self._thumb_pixmap)
        self._update_ambient_palette(self._thumb_pixmap)
        self.update()

    def update_display_title(self, title: str):
        self._title = title.strip()
        self.update()

    def update_display_artist(self, artist: str):
        self._artist = artist.strip()
        self.update()

    def update_song_info(self, title: str, artist: str):
        self._title = title.strip()
        self._artist = artist.strip()
        self.update()

    def set_lyrics(self, lyrics: Optional[ParsedLyrics]):
        self._lyrics = lyrics
        self._canvas.set_lyrics(lyrics)
        self.update()

    def set_current_time(self, elapsed_ms: int, idx: int):
        self._cur_index = idx
        self._elapsed_ms = elapsed_ms
        self._canvas.set_current_time(elapsed_ms, idx)

    def _load_theme_colors(self):
        self._color_accent = QColor(settings.get_theme_color("accent", "#78CDFF"))
        self._color_prog_start = QColor(settings.get_theme_color("progress_start", "#FFFFFF"))
        self._color_prog_end = QColor(settings.get_theme_color("progress_end", "#A0E6FF"))
        self._color_inact = QColor(settings.get_theme_color("lyric_inactive", "#A0A8B8"))

    def set_duration(self, duration_ms: int) -> None:
        duration_ms = max(0, int(duration_ms))
        if duration_ms != self._total_ms:
            self._total_ms = duration_ms
            self.update()

    def _is_pure_music(self) -> bool:
        if self._lyrics and self._lyrics.is_instrumental:
            return True
        return False

    def set_current_index(self, idx: int):
        self._cur_index = idx
        self._canvas.set_current_index(idx)

    def _on_fs_tick(self) -> None:
        is_animating = False

        diff_p = self._target_loading_progress - self._loading_progress
        if abs(diff_p) > 0.001:
            self._loading_progress += diff_p * 0.075
            is_animating = True
        else:
            self._loading_progress = self._target_loading_progress

        diff_a = self._target_cover_alpha - self._cover_alpha
        if abs(diff_a) > 0.005:
            self._cover_alpha += diff_a * 0.16
            is_animating = True
        else:
            self._cover_alpha = self._target_cover_alpha

        diff_bg = 1.0 - self._bg_crossfade
        if diff_bg > 0.01:
            self._bg_crossfade += diff_bg * 0.12
            is_animating = True
        else:
            self._bg_crossfade = 1.0

        # 封面高清平滑淡入
        if self._thumb_crossfade < 1.0:
            diff_cf = 1.0 - self._thumb_crossfade
            if diff_cf > 0.01:
                self._thumb_crossfade += diff_cf * 0.16
                is_animating = True
            else:
                self._thumb_crossfade = 1.0
                self._prev_thumb_pixmap = None

        spinner_needed = self._loading_progress > 0.02 and (self._loading_progress < 0.999 or self._cover_alpha < 0.98)
        if spinner_needed:
            self._loading_spinner_angle = (self._loading_spinner_angle + 2.5) % 360.0
            is_animating = True

        if is_animating:
            self.update()

    def reset_loading_progress(self, keep_cover: bool = False) -> None:
        self._loading_progress = 0.0
        self._target_loading_progress = 0.10
        if not keep_cover:
            self._cover_alpha = 0.0
            self._target_cover_alpha = 0.0
        self._loading_spinner_angle = 0.0
        self.update()

    def set_target_loading_progress(self, val: float) -> None:
        self._target_loading_progress = max(0.0, min(1.0, float(val)))

    def set_playing(self, playing: bool):
        self._is_playing = playing
        self._canvas.set_playing(playing)
        self.update()

    # ── 绘制 ─────────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        w, h = self.width(), self.height()

        # ── 1. 全画幅专辑封面大半径高斯模糊背景 ──
        if self._curr_bg_pixmap and not self._curr_bg_pixmap.isNull():
            if self._prev_bg_pixmap and not self._prev_bg_pixmap.isNull() and self._bg_crossfade < 1.0:
                painter.drawPixmap(0, 0, w, h, self._prev_bg_pixmap)
                painter.save()
                painter.setOpacity(self._bg_crossfade)
                painter.drawPixmap(0, 0, w, h, self._curr_bg_pixmap)
                painter.restore()
            else:
                painter.drawPixmap(0, 0, w, h, self._curr_bg_pixmap)

            # ── 2. 半透明暗色蒙层 ──
            painter.fillRect(0, 0, w, h, QColor(10, 12, 16, 115))
        else:
            # 容错降级：无封面时的默认深色背景
            painter.fillRect(0, 0, w, h, QColor(16, 17, 23))
            glow_center = QRadialGradient(w * 0.5, h * 0.45, max(w, h) * 0.55)
            c_c = self._ambient_col_center
            glow_center.setColorAt(0.0, QColor(c_c.red(), c_c.green(), c_c.blue(), 75))
            glow_center.setColorAt(0.40, QColor(c_c.red(), c_c.green(), c_c.blue(), 30))
            glow_center.setColorAt(0.85, QColor(c_c.red(), c_c.green(), c_c.blue(), 6))
            glow_center.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.fillRect(0, 0, w, h, QBrush(glow_center))

        # ── 3. 顶部与底部暗角渐变 ──
        top_grad = QLinearGradient(0, 0, 0, 140)
        top_grad.setColorAt(0.0, QColor(8, 10, 14, 110))
        top_grad.setColorAt(1.0, QColor(8, 10, 14, 0))
        painter.fillRect(0, 0, w, 140, QBrush(top_grad))

        bot_grad = QLinearGradient(0, h - 140, 0, h)
        bot_grad.setColorAt(0.0, QColor(8, 10, 14, 0))
        bot_grad.setColorAt(1.0, QColor(8, 10, 14, 150))
        painter.fillRect(0, h - 140, w, 140, QBrush(bot_grad))

        # ── 3. 左上角：封面卡片 + 歌曲信息 ─────────────────────────────────
        thumb_size = 64
        margin = 28
        cover_rect = QRectF(margin, margin, thumb_size, thumb_size)

        # 绘制封面卡片占位底色
        placeholder_path = QPainterPath()
        placeholder_path.addRoundedRect(cover_rect, 12.0, 12.0)
        painter.fillPath(placeholder_path, QColor(255, 255, 255, 30))

        # 若加载未完成或封面渐入中，绘制加载进度圆环
        if self._loading_progress > 0.02 and (self._loading_progress < 0.999 or self._cover_alpha < 0.98):
            center_pt = cover_rect.center()
            radius = 16.0
            ring_rect = QRectF(center_pt.x() - radius, center_pt.y() - radius, radius * 2.0, radius * 2.0)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            # 1. 轨道底环
            track_pen = QPen(QColor(255, 255, 255, 35))
            track_pen.setWidthF(3.0)
            track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(track_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(ring_rect)

            # 2. 动态进度光弧
            arc_pen = QPen(self._color_accent)
            arc_pen.setWidthF(3.0)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc_pen)

            start_angle = int((90.0 - self._loading_spinner_angle * 0.15) * 16.0)
            span_angle = -int(max(8.0, min(360.0, self._loading_progress * 360.0)) * 16.0)
            painter.drawArc(ring_rect, start_angle, span_angle)

            painter.restore()

        # 封面与背景微光渐入渲染
        if self._thumb_pixmap and self._cover_alpha > 0.01:
            # 封面环境微光
            glow_rect = cover_rect.adjusted(-6, -6, 6, 6)
            glow_pix = self._thumb_pixmap.scaled(
                16, 16,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ).scaled(
                int(glow_rect.width()), int(glow_rect.height()),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            glow_path = QPainterPath()
            glow_path.addRoundedRect(glow_rect, 16.0, 16.0)
            painter.save()
            painter.setClipPath(glow_path)
            painter.setOpacity(0.35 * self._cover_alpha)
            painter.drawPixmap(int(glow_rect.x()), int(glow_rect.y()), glow_pix)
            painter.restore()

            # 圆角封面
            path = QPainterPath()
            path.addRoundedRect(cover_rect, 12.0, 12.0)
            painter.save()
            painter.setClipPath(path)
            target_rect = cover_rect.toRect()

            if self._prev_thumb_pixmap and not self._prev_thumb_pixmap.isNull() and self._thumb_crossfade < 1.0:
                painter.setOpacity(self._cover_alpha)
                scaled_prev = self._prev_thumb_pixmap.scaled(
                    thumb_size * 2, thumb_size * 2,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                painter.drawPixmap(target_rect, scaled_prev)

                painter.setOpacity(self._cover_alpha * self._thumb_crossfade)
                scaled_curr = self._thumb_pixmap.scaled(
                    thumb_size * 2, thumb_size * 2,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                painter.drawPixmap(target_rect, scaled_curr)
            else:
                painter.setOpacity(self._cover_alpha)
                scaled_thumb = self._thumb_pixmap.scaled(
                    thumb_size * 2, thumb_size * 2,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                painter.drawPixmap(target_rect, scaled_thumb)

            painter.restore()

        tx = margin + thumb_size + 16
        painter.setFont(_make_font(18, bold=True))
        painter.setPen(QColor(255, 255, 255, 240))
        painter.drawText(tx, margin + 26, self._title or "正在播放")

        painter.setFont(_make_font(13, bold=False))
        if self._lyrics and self._lyrics.is_instrumental:
            painter.setPen(QColor(120, 205, 255, 220))
        else:
            painter.setPen(QColor(255, 255, 255, 130))
        painter.drawText(tx, margin + 48, self._artist or "")

        if self._lyrics and self._lyrics.is_instrumental:
            avail_size = min(float(w) * 0.42, float(h) * 0.46)
            center_size = float(min(360, max(180, int(avail_size))))
            cx = (float(w) - center_size) / 2.0
            cy = (float(h) - center_size) / 2.0
            center_rect = QRectF(cx, cy, center_size, center_size)

            if not self._thumb_pixmap or self._cover_alpha <= 0.01:
                placeholder_path = QPainterPath()
                placeholder_path.addRoundedRect(center_rect, 16.0, 16.0)
                painter.fillPath(placeholder_path, QColor(255, 255, 255, 20))

            if self._thumb_pixmap and self._cover_alpha > 0.01:
                base_center_alpha = 0.30 * self._cover_alpha

                glow_rect = center_rect.adjusted(-8, -8, 8, 8)
                glow_pix = self._thumb_pixmap.scaled(
                    16, 16,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ).scaled(
                    int(glow_rect.width()), int(glow_rect.height()),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                glow_path = QPainterPath()
                glow_path.addRoundedRect(glow_rect, 22.0, 22.0)
                painter.save()
                painter.setClipPath(glow_path)
                painter.setOpacity(0.12 * self._cover_alpha)
                painter.drawPixmap(int(glow_rect.x()), int(glow_rect.y()), glow_pix)
                painter.restore()

                path = QPainterPath()
                path.addRoundedRect(center_rect, 16.0, 16.0)
                painter.save()
                painter.setClipPath(path)
                target_rect = center_rect.toRect()

                if self._prev_thumb_pixmap and not self._prev_thumb_pixmap.isNull() and self._thumb_crossfade < 1.0:
                    painter.setOpacity(base_center_alpha)
                    scaled_prev = self._prev_thumb_pixmap.scaled(
                        target_rect.size() * 2,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    painter.drawPixmap(target_rect, scaled_prev)

                    painter.setOpacity(base_center_alpha * self._thumb_crossfade)
                    scaled_curr = self._thumb_pixmap.scaled(
                        target_rect.size() * 2,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    painter.drawPixmap(target_rect, scaled_curr)
                else:
                    painter.setOpacity(base_center_alpha)
                    scaled_thumb = self._thumb_pixmap.scaled(
                        target_rect.size() * 2,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    painter.drawPixmap(target_rect, scaled_thumb)

                painter.restore()

            if self._loading_progress > 0.02 and (self._loading_progress < 0.999 or self._cover_alpha < 0.98):
                center_pt = center_rect.center()
                radius = 20.0
                ring_rect = QRectF(center_pt.x() - radius, center_pt.y() - radius, radius * 2.0, radius * 2.0)

                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                track_pen = QPen(QColor(255, 255, 255, 35))
                track_pen.setWidthF(3.0)
                track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(track_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(ring_rect)

                arc_pen = QPen(self._color_accent)
                arc_pen.setWidthF(3.0)
                arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(arc_pen)

                start_angle = int((90.0 - self._loading_spinner_angle * 0.15) * 16.0)
                span_angle = -int(max(8.0, min(360.0, self._loading_progress * 360.0)) * 16.0)
                painter.drawArc(ring_rect, start_angle, span_angle)
                painter.restore()

        hints_font = _make_font(11, bold=False)
        painter.setFont(hints_font)
        painter.setPen(QColor(255, 255, 255, 75))
        hints = "← -0.1s  |  → +0.1s  |  Space 播放/暂停  |  S 设置  |  O 桌面悬浮条  |  Esc 退出全屏"
        fm = QFontMetrics(hints_font)
        painter.drawText((w - fm.horizontalAdvance(hints)) // 2, h - 22, hints)

        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._canvas.setGeometry(self.rect())
        if self._thumb_pixmap and not self._thumb_pixmap.isNull():
            self._curr_bg_pixmap = self._generate_blurred_bg(self._thumb_pixmap)

    # ── 键盘 ─────────────────────────────────────────────────────────────────
    def keyPressEvent(self, e: QKeyEvent):
        key = e.key()
        if key == Qt.Key.Key_Escape or key == Qt.Key.Key_O:
            self._ctrl.switch_mode("overlay")
        elif key == Qt.Key.Key_S:
            self._ctrl.open_settings()
        elif key == Qt.Key.Key_Left:
            self._ctrl.smtc.adjust_offset(-100)
        elif key == Qt.Key.Key_Right:
            self._ctrl.smtc.adjust_offset(100)
        elif key == Qt.Key.Key_Space:
            self._ctrl.smtc.toggle_play_pause()
        elif key == Qt.Key.Key_F11:
            self._ctrl.switch_mode("overlay")
        else:
            super().keyPressEvent(e)

    # ── 右键菜单 ─────────────────────────────────────────────────────────────
    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: rgba(26, 28, 40, 0.95); color: #fff;
                    border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 10px;
                    padding: 6px; font-size: 13px; }
            QMenu::item { padding: 6px 24px; border-radius: 6px; }
            QMenu::item:selected { background: rgba(255, 255, 255, 0.15); }
        """)
        act_ov = menu.addAction("🪟  悬浮条模式")
        act_sett = menu.addAction("⚙  设置...")
        menu.addSeparator()
        label = ("✓" if self._canvas._show_translation else " ") + "  显示译文"
        act_tr = menu.addAction(label)
        label_ro = ("✓" if self._canvas._show_romaji else " ") + "  显示罗马音"
        act_ro = menu.addAction(label_ro)
        label_sec = ("✓" if settings.get_parse_sections() else " ") + "  段落解析"
        act_sec = menu.addAction(label_sec)
        menu.addSeparator()
        act_quit = menu.addAction("✕  退出")

        act_ov.triggered.connect(lambda: self._ctrl.switch_mode("overlay"))
        act_sett.triggered.connect(self._ctrl.open_settings)
        act_tr.triggered.connect(self._toggle_translation)
        act_ro.triggered.connect(self._toggle_romaji)
        act_sec.triggered.connect(self._toggle_parse_sections)
        act_quit.triggered.connect(QApplication.quit)
        menu.exec(e.globalPos())

    def _toggle_translation(self):
        show = not self._canvas._show_translation
        self._canvas.set_show_translation(show)
        settings.set_show_translation(show)

    def _toggle_romaji(self):
        show = not self._canvas._show_romaji
        self._canvas.set_show_romaji(show)
        settings.set_show_romaji(show)

    def _toggle_parse_sections(self):
        cur = settings.get_parse_sections()
        settings.set_parse_sections(not cur)
        self._canvas.set_parse_sections(not cur)
        if hasattr(self._ctrl, "_reload_current_song_lyrics"):
            self._ctrl._reload_current_song_lyrics()

    def reload_settings(self):
        self._load_theme_colors()
        self._canvas.reload_settings()
        self.update()
