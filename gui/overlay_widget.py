"""
overlay_widget.py — 桌面悬浮歌词组件
特性：
  - 字体：支持自定义字体栈与回退机制
  - 进度：基于 QTimer 驱动的时间插值与歌词进度渲染
  - 水平滚动：长歌词随播放进度自动水平滚动居中
  - 边缘虚化：两端采用 Alpha 渐变遮罩处理溢出文本
  - 状态展示：首句歌词前展示专辑封面与歌曲信息卡片，纯音乐模式显示提示
  - 交互：支持透明度调节、拖拽移动与窗口尺寸调整
"""
from __future__ import annotations

import math
import time
from typing import Optional

from PyQt6.QtCore import Qt, QRectF, QTimer, QPoint, QSize
from PyQt6.QtGui import (
    QColor, QPainter, QFont, QFontMetrics, QLinearGradient,
    QPainterPath, QMouseEvent, QWheelEvent, QKeyEvent, QPen, QBrush,
    QImage, QPixmap,
)
from PyQt6.QtWidgets import QWidget, QApplication, QMenu

try:
    from core import settings, font_manager
    from core.lyrics_parser import ParsedLyrics
except ImportError:
    import settings
    import font_manager
    from lyrics_parser import ParsedLyrics

GRIP_SIZE = 22      # 右下角半矩形缩放热区尺寸
FADE_MARGIN = 48.0  # 左右两端虚化遮罩宽度 (像素)


class OverlayWidget(QWidget):
    """桌面悬浮歌词窗口部件"""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._lyrics: Optional[ParsedLyrics] = None
        self._cur_index: int = -1
        self._opacity: float = settings.get_opacity()
        self._is_playing: bool = False
        self._show_translation: bool = settings.get_show_translation()
        self._show_line_progress: bool = settings.get_show_line_progress()
        self._status_text: str = "LyrikFlow"

        # 歌曲信息（首句歌词前展示）
        self._song_title: str = ""
        self._song_artist: str = ""
        self._thumb_pixmap: Optional[QPixmap] = None

        # 拖拽移动与右下角缩放状态
        self._is_dragging: bool = False
        self._drag_offset: Optional[QPoint] = None
        self._is_resizing: bool = False
        self._resize_start_pos: Optional[QPoint] = None
        self._orig_size: Optional[QSize] = None
        self._hover_grip: bool = False

        # 60FPS 本地高精度连续时间插值引擎
        self._base_ms: float = 0.0
        self._base_wall_time: float = time.monotonic()

        # 换句流体弹簧动画状态 (0.0 -> 1.0)
        self._anim_progress: float = 1.0
        self._prev_main_text: str = ""
        self._prev_trans_text: str = ""

        # 超长歌词自适应水平平滑滚动系统
        self._scroll_x: float = 0.0
        self._target_scroll_x: float = 0.0

        # 字体排印：Zen Maru Gothic / Comfortaa + 统一退避字体栈
        self._font_size = settings.get_font_size_current()
        self._font_main = self._create_round_font(self._font_size, bold=True)
        self._font_sub = self._create_round_font(settings.get_font_size_context(), bold=False)
        self._is_verbatim_song: bool = False

        # 封面加载圆环进度系统 (0.0 ~ 1.0，任务点平滑推进)
        self._loading_progress: float = 1.0
        self._target_loading_progress: float = 1.0
        self._loading_spinner_angle: float = 0.0
        self._cover_alpha: float = 1.0
        self._target_cover_alpha: float = 1.0

        # 60FPS (16ms) 全局渲染驱动定时器
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(16)
        self._render_timer.timeout.connect(self._on_render_tick)
        self._render_timer.start()

        # 100% 纯透明无边框窗口
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setMouseTracking(True)  # 开启全局鼠标悬停跟踪

        geo = settings.get_overlay_geometry()
        if geo:
            self.setGeometry(*geo)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            win_w, win_h = 1080, 130
            x = screen.x() + (screen.width() - win_w) // 2
            y = screen.y() + int(screen.height() * 0.74)
            self.setGeometry(x, y, win_w, win_h)

    # ── 公共接口 ─────────────────────────────────────────────────────────────
    def set_song(self, title: str, artist: str, thumb_bytes: bytes) -> None:
        """设置当前歌曲信息与封面缩略图"""
        self._song_title = title.strip()
        self._song_artist = artist.strip()
        if thumb_bytes:
            img = QImage.fromData(bytes(thumb_bytes))
            if not img.isNull():
                self._thumb_pixmap = QPixmap.fromImage(img)
                self._cover_alpha = 1.0
                self._target_cover_alpha = 1.0
                self._loading_progress = 1.0
                self._target_loading_progress = 1.0
            else:
                self._thumb_pixmap = None
                self._cover_alpha = 0.0
                self._target_cover_alpha = 0.0
        else:
            self._thumb_pixmap = None
            self._cover_alpha = 0.0
            self._target_cover_alpha = 0.0
        self.update()

    def update_hd_cover(self, hd_cover_bytes: bytes) -> None:
        """从网易云后台替换为 300x300 超清原画专辑封面，并开启封面淡入与圆环补满"""
        if hd_cover_bytes:
            img = QImage.fromData(bytes(hd_cover_bytes))
            if not img.isNull():
                self._thumb_pixmap = QPixmap.fromImage(img)
                self._cover_alpha = 0.0
                self._target_cover_alpha = 1.0
                self._target_loading_progress = 1.0
                self.update()

    def update_display_title(self, title: str) -> None:
        """更新歌曲展示标题（如异步解析到副标题/别名）"""
        self._song_title = title.strip()
        self.update()

    def update_display_artist(self, artist: str) -> None:
        """更新歌手行展示内容（如追加副标题/别名）"""
        self._song_artist = artist.strip()
        self.update()

    def update_song_info(self, title: str, artist: str) -> None:
        """同步更新歌曲标题与歌手行展示内容"""
        self._song_title = title.strip()
        self._song_artist = artist.strip()
        self.update()

    def reset_loading_progress(self) -> None:
        """重置加载进度，开启圆环动画"""
        self._loading_progress = 0.0
        self._target_loading_progress = 0.10
        self._cover_alpha = 0.0
        self._target_cover_alpha = 0.0
        self._loading_spinner_angle = 0.0
        self.update()

    def set_target_loading_progress(self, val: float) -> None:
        """设置平滑推进的目标进度 (0.0 ~ 1.0)"""
        self._target_loading_progress = max(0.0, min(1.0, float(val)))

    def set_lyrics(self, lyrics: Optional[ParsedLyrics]) -> None:
        self._lyrics = lyrics
        self._is_verbatim_song = bool(
            lyrics and any(bool(line.words) for line in lyrics.lines)
        )
        self._cur_index = -1
        self._anim_progress = 1.0
        self._prev_main_text = ""
        self._prev_trans_text = ""
        self._scroll_x = 0.0
        self._target_scroll_x = 0.0
        self.update()

    def set_current_time(self, elapsed_ms: int, idx: int) -> None:
        self._base_ms = float(elapsed_ms)
        self._base_wall_time = time.monotonic()

        if idx != self._cur_index:
            if self._lyrics and 0 <= self._cur_index < len(self._lyrics.lines):
                prev_line = self._lyrics.lines[self._cur_index]
                self._prev_main_text = prev_line.text.strip()
                self._prev_trans_text = prev_line.translation.strip()
            else:
                self._prev_main_text = ""
                self._prev_trans_text = ""

            self._cur_index = idx
            self._anim_progress = 0.0
            # 换句时重置水平滚动
            self._scroll_x = 0.0
            self._target_scroll_x = 0.0

    def set_playing(self, playing: bool) -> None:
        self._is_playing = playing
        self._base_wall_time = time.monotonic()

    def set_status_text(self, text: str) -> None:
        self._status_text = text

    # ── 获取当前 60FPS 绝对平滑连续毫秒数 ────────────────────────────────────
    def _get_live_elapsed_ms(self) -> float:
        if self._is_playing:
            return self._base_ms + (time.monotonic() - self._base_wall_time) * 1000.0
        return self._base_ms

    # ── 60FPS 刷新 tick ──────────────────────────────────────────────────────
    def _on_render_tick(self) -> None:
        # 换行微浮动动画
        if self._anim_progress < 1.0:
            self._anim_progress = min(1.0, self._anim_progress + 0.065)

        # 超长歌词水平滚动插值
        diff = self._target_scroll_x - self._scroll_x
        if abs(diff) > 0.05:
            self._scroll_x += diff * 0.12
        else:
            self._scroll_x = self._target_scroll_x

        # 封面加载圆环进度插值 (Lerp)
        diff_p = self._target_loading_progress - self._loading_progress
        if abs(diff_p) > 0.001:
            self._loading_progress += diff_p * 0.075
        else:
            self._loading_progress = self._target_loading_progress

        # 封面渐入透明度插值 (0.0 ~ 1.0)
        diff_a = self._target_cover_alpha - self._cover_alpha
        if abs(diff_a) > 0.005:
            self._cover_alpha += diff_a * 0.16
        else:
            self._cover_alpha = self._target_cover_alpha

        self._loading_spinner_angle = (self._loading_spinner_angle + 2.5) % 360.0

        self.update()

    # ── 绘制主入口 ───────────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w, h = self.width(), self.height()
        live_ms = self._get_live_elapsed_ms()

        # 判断是否为首句歌词唱响前（前奏 / 加载中）
        first_line_time = 0
        if self._lyrics and self._lyrics.lines:
            first_line_time = self._lyrics.lines[0].time_ms

        is_before_first_line = (
            not self._lyrics
            or self._cur_index < 0
            or (live_ms < first_line_time and self._cur_index == 0)
        )

        is_instrumental = bool(self._lyrics and self._lyrics.is_instrumental)

        if is_instrumental or (is_before_first_line and (self._song_title or self._thumb_pixmap)):
            # ── 状态 A：纯音乐或首句前展示歌曲信息卡片 ──
            self._render_song_intro_card(painter, w, h, is_instrumental=is_instrumental)
        elif not self._lyrics or self._cur_index < 0 or not (0 <= self._cur_index < len(self._lyrics.lines)):
            # 待机占位
            self._draw_standby(painter, w, h)
        else:
            # ── 状态 B：歌词唱响阶段，在独立图层渲染并应用左右两端虚化遮罩 ──
            self._render_lyrics_with_edge_feather(painter, w, h, live_ms)

        # ── 绘制右下角缩放控件 ─────────────────────────────────────────────
        self._draw_resize_grip(painter, w, h)

    # ── 绘制首句前歌曲信息卡片 ─────────────────────────────────────────────
    def _render_song_intro_card(self, painter: QPainter, w: int, h: int, is_instrumental: bool = False) -> None:
        title = self._song_title or "正在播放"
        artist = self._song_artist or ""

        fm_m = QFontMetrics(self._font_main)
        fm_s = QFontMetrics(self._font_sub)

        cover_size = 62.0
        spacing = 18.0

        title_w = fm_m.horizontalAdvance(title)
        artist_w = fm_s.horizontalAdvance(artist) if artist else 0
        text_block_w = max(title_w, artist_w)

        total_w = cover_size + spacing + text_block_w
        start_x = max(24.0, (w - total_w) / 2.0)
        center_y = h / 2.0
        cover_rect = QRectF(start_x, center_y - cover_size / 2.0, cover_size, cover_size)

        # 1. 绘制封面背景卡片
        placeholder_path = QPainterPath()
        placeholder_path.addRoundedRect(cover_rect, 14.0, 14.0)
        painter.fillPath(placeholder_path, QColor(255, 255, 255, int(self._opacity * 28)))

        # 若加载未完成或封面渐入中，绘制加载进度圆环
        if self._loading_progress > 0.02 and (self._loading_progress < 0.999 or self._cover_alpha < 0.98):
            center_pt = cover_rect.center()
            radius = 13.0
            ring_rect = QRectF(center_pt.x() - radius, center_pt.y() - radius, radius * 2.0, radius * 2.0)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            # 轨道底环 (Frosted Track)
            track_pen = QPen(QColor(255, 255, 255, int(self._opacity * 35)))
            track_pen.setWidthF(2.5)
            track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(track_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(ring_rect)

            # 动态进度光弧 (Smooth Progress Arc，顺时针补充至满)
            arc_pen = QPen(QColor(120, 205, 255, int(self._opacity * 230)))  # 柔和灵动冰蓝高亮
            arc_pen.setWidthF(2.5)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc_pen)

            # 从顶部 12 点钟（90度）顺时针延伸，并伴随微光自转动效
            start_angle = int((90.0 - self._loading_spinner_angle * 0.15) * 16.0)
            span_angle = -int(max(8.0, min(360.0, self._loading_progress * 360.0)) * 16.0)
            painter.drawArc(ring_rect, start_angle, span_angle)

            painter.restore()

        # 封面与环境微光：平滑渐入渲染 (渐入速度比进度条满更快，两者自然呼应交织)
        if self._thumb_pixmap and self._cover_alpha > 0.01:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

            # ── A. 底层环境彩色光晕 ──
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
            glow_path.addRoundedRect(glow_rect, 18.0, 18.0)
            painter.save()
            painter.setClipPath(glow_path)
            painter.setOpacity(self._opacity * 0.28 * self._cover_alpha)
            painter.drawPixmap(int(glow_rect.x()), int(glow_rect.y()), glow_pix)
            painter.restore()

            # ── B. 主封面：高清平滑圆角 ──
            path = QPainterPath()
            path.addRoundedRect(cover_rect, 14.0, 14.0)
            painter.save()
            painter.setClipPath(path)
            painter.setOpacity(self._opacity * self._cover_alpha)

            scaled_thumb = self._thumb_pixmap.scaled(
                int(cover_size * 2), int(cover_size * 2),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(
                QRectF(cover_rect.x(), cover_rect.y(), cover_size, cover_size).toRect(),
                scaled_thumb,
            )
            painter.restore()

            painter.restore()

        text_x = start_x + cover_size + spacing

        # 2. 绘制歌名与歌手
        has_sub = bool(artist)
        text_h = fm_m.height() + (fm_s.height() + 4 if has_sub else 0)
        t_base_y = (h - text_h) / 2.0 + fm_m.ascent()

        painter.setFont(self._font_main)
        painter.setPen(QColor(255, 255, 255, int(self._opacity * 255)))
        painter.drawText(int(text_x), int(t_base_y), title)

        if has_sub:
            s_base_y = t_base_y + fm_m.descent() + 4 + fm_s.ascent()
            painter.setFont(self._font_sub)
            if is_instrumental:
                painter.setPen(QColor(120, 205, 255, int(self._opacity * 230)))  # 纯音乐状态使用强调色
            else:
                painter.setPen(QColor(255, 255, 255, int(self._opacity * 130)))
            painter.drawText(int(text_x), int(s_base_y), artist)

    # ── 歌词展示阶段（支持边缘 Alpha 渐变遮罩）─────────────
    def _render_lyrics_with_edge_feather(self, painter: QPainter, w: int, h: int, live_ms: float) -> None:
        current_line = self._lyrics.lines[self._cur_index]
        curr_text = current_line.text.strip()
        if not curr_text:
            return

        fm_m = QFontMetrics(self._font_main)
        fm_s = QFontMetrics(self._font_sub)

        # 检查是否溢出需要边缘遮罩虚化
        main_w = fm_m.horizontalAdvance(curr_text)
        view_w = w - FADE_MARGIN * 2.0
        has_trans = bool(current_line.translation.strip() and self._show_translation)
        trans_w = fm_s.horizontalAdvance(current_line.translation.strip()) if has_trans else 0

        prev_overflow = False
        if self._prev_main_text and self._anim_progress < 0.85:
            if fm_m.horizontalAdvance(self._prev_main_text) > view_w:
                prev_overflow = True

        need_feather = (main_w > view_w) or (trans_w > view_w) or (self._scroll_x > 0.5) or prev_overflow

        if not need_feather:
            # ── 文本未溢出：直接在主 painter 绘制 ──
            self._paint_lyric_elements(painter, w, h, live_ms, fm_m, fm_s, current_line, curr_text)
            return

        # ── 溢出滚动路径：创建离屏缓冲区应用两端渐变遮罩 ──
        dpr = self.devicePixelRatioF()
        pw = int(math.ceil(w * dpr))
        ph = int(math.ceil(h * dpr))
        layer_img = QImage(pw, ph, QImage.Format.Format_ARGB32_Premultiplied)
        layer_img.setDevicePixelRatio(dpr)
        layer_img.fill(Qt.GlobalColor.transparent)

        lp = QPainter(layer_img)
        lp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        lp.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        lp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self._paint_lyric_elements(lp, w, h, live_ms, fm_m, fm_s, current_line, curr_text)

        # 左右两端应用 Alpha 渐变遮罩
        lp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        mask_grad = QLinearGradient(0, 0, w, 0)
        p_left = min(0.4, FADE_MARGIN / float(w))
        p_right = max(0.6, (w - FADE_MARGIN) / float(w))

        mask_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        mask_grad.setColorAt(p_left, QColor(0, 0, 0, 255))
        mask_grad.setColorAt(p_right, QColor(0, 0, 0, 255))
        mask_grad.setColorAt(1.0, QColor(0, 0, 0, 0))

        lp.fillRect(0, 0, w, h, QBrush(mask_grad))
        lp.end()

        painter.drawImage(0, 0, layer_img)

    def _paint_lyric_elements(
        self,
        painter: QPainter,
        w: int,
        h: int,
        live_ms: float,
        fm_m: QFontMetrics,
        fm_s: QFontMetrics,
        current_line,
        curr_text: str,
    ) -> None:
        # 缓动曲线计算
        t = self._anim_progress
        eased_in = 1.0 - math.pow(1.0 - t, 3)

        # 1. 上一句渐出过渡
        if self._prev_main_text and t < 0.85:
            prev_alpha = (1.0 - (t / 0.85)) * self._opacity
            if prev_alpha > 0.02:
                prev_drift = t * 12.0
                self._render_line(
                    painter,
                    text=self._prev_main_text,
                    trans=self._prev_trans_text,
                    w=w, h=h,
                    fm_m=fm_m, fm_s=fm_s,
                    center_y_offset=-prev_drift,
                    alpha=prev_alpha * 0.35,
                    live_ms=live_ms,
                    words=None,
                    force_full_progress=True,
                )

        # 2. 当前句登场
        curr_alpha = eased_in * self._opacity
        curr_float = (1.0 - eased_in) * 8.0

        self._render_line(
            painter,
            text=curr_text,
            trans=current_line.translation.strip() if self._show_translation else "",
            w=w, h=h,
            fm_m=fm_m, fm_s=fm_s,
            center_y_offset=curr_float,
            alpha=curr_alpha,
            live_ms=live_ms,
            words=current_line.words if current_line.words else None,
            force_full_progress=False,
            current_line_obj=current_line,
        )

    # ── 单句逐字进度及自适应水平滚动核心渲染逻辑 ─────────────────────────────
    def _render_line(
        self,
        painter: QPainter,
        text: str,
        trans: str,
        w: int,
        h: int,
        fm_m: QFontMetrics,
        fm_s: QFontMetrics,
        center_y_offset: float,
        alpha: float,
        live_ms: float,
        words: Optional[list],
        force_full_progress: bool = False,
        current_line_obj=None,
    ) -> None:
        has_trans = bool(trans and self._show_translation)
        total_h = fm_m.height() + (fm_s.height() + 6 if has_trans else 0)

        base_y = (h - total_h) / 2.0 + center_y_offset
        main_baseline = base_y + fm_m.ascent()

        main_w = fm_m.horizontalAdvance(text)
        view_w = w - FADE_MARGIN * 2.0

        # ── 1. 超长歌词自适应水平平滑滚动 (Auto-scroll Flow) ──
        if main_w > view_w:
            # 计算当前焦点在歌词文本内部的相对像素位置
            focus_offset_in_text = 0.0
            if words:
                curr_w_x = 0.0
                for wd in words:
                    wd_w = fm_m.horizontalAdvance(wd.text)
                    w_start = wd.time_ms
                    w_dur = max(1, wd.duration_ms)
                    w_end = w_start + w_dur
                    if live_ms >= w_end:
                        curr_w_x += wd_w
                    elif live_ms >= w_start:
                        curr_w_x += wd_w * min(1.0, max(0.0, (live_ms - w_start) / float(w_dur)))
                        break
                    else:
                        break
                focus_offset_in_text = curr_w_x
            elif current_line_obj:
                dur = max(1000, current_line_obj.duration_ms)
                r = min(1.0, max(0.0, (live_ms - current_line_obj.time_ms) / float(dur)))
                focus_offset_in_text = main_w * r

            # 计算目标滚动位移：让焦点尽量保持在中央视野
            max_scroll = main_w - view_w
            target_shift = focus_offset_in_text - (view_w / 2.0)
            self._target_scroll_x = max(0.0, min(max_scroll, target_shift))

            # 应用当前平滑滚动偏移
            start_x = FADE_MARGIN - self._scroll_x
        else:
            # 未超出可视范围：居中对齐，无需滚动
            self._target_scroll_x = 0.0
            start_x = (w - main_w) / 2.0

        # ── 2. 计算逐字进度的绝对染色坐标 (progress_x) ──
        if force_full_progress:
            progress_x = start_x + main_w
        elif self._is_verbatim_song:
            if words:
                curr_px = start_x
                for wd in words:
                    wd_w = fm_m.horizontalAdvance(wd.text)
                    w_start = wd.time_ms
                    w_dur = max(1, wd.duration_ms)
                    w_end = w_start + w_dur

                    if live_ms >= w_end:
                        curr_px += wd_w
                    elif live_ms >= w_start:
                        r = (live_ms - w_start) / float(w_dur)
                        curr_px += wd_w * min(1.0, max(0.0, r))
                        break
                    else:
                        break
                progress_x = curr_px
            elif current_line_obj:
                dur = max(1000, current_line_obj.duration_ms)
                r = min(1.0, max(0.0, (live_ms - current_line_obj.time_ms) / float(dur)))
                progress_x = start_x + main_w * r
            else:
                progress_x = start_x
        else:
            progress_x = start_x

        # ── 3. 样式分支：逐字歌曲 vs 非逐字歌曲（切歌时判定，歌曲全程统一）──
        if self._is_verbatim_song:
            # ── 模式 A：原生逐字歌词，流光扫掠染色 ──
            painter.setFont(self._font_main)
            base_col = QColor(255, 255, 255, int(alpha * 85))
            painter.setPen(base_col)
            painter.drawText(int(start_x), int(main_baseline), text)

            if progress_x > start_x:
                painter.save()
                painter.setClipRect(QRectF(0, 0, progress_x + 16, h))

                feather_px = 16.0
                sweep = QLinearGradient(start_x, 0, max(start_x + 10.0, progress_x + feather_px), 0)
                sweep.setColorAt(0.0, QColor(255, 255, 255, int(alpha * 255)))

                dist = max(1.0, progress_x - start_x)
                p_start = max(0.0, (dist - feather_px) / (dist + feather_px))
                p_end = min(1.0, dist / (dist + feather_px))

                sweep.setColorAt(p_start, QColor(255, 255, 255, int(alpha * 255)))
                sweep.setColorAt(p_end, QColor(255, 255, 255, int(alpha * 160)))
                sweep.setColorAt(1.0, QColor(255, 255, 255, 0))

                painter.setPen(QPen(QBrush(sweep), 0))
                painter.drawText(int(start_x), int(main_baseline), text)

                bloom_col = QColor(255, 255, 255, int(alpha * 36))
                painter.setPen(bloom_col)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    painter.drawText(int(start_x + dx), int(main_baseline + dy), text)

                painter.restore()
        else:
            # ── 模式 B：非逐字歌词，整句纯白高亮 + 下方圆润单句胶囊进度条 ──
            painter.setFont(self._font_main)
            painter.setPen(QColor(255, 255, 255, int(alpha * 240)))
            painter.drawText(int(start_x), int(main_baseline), text)

            bloom_col = QColor(255, 255, 255, int(alpha * 30))
            painter.setPen(bloom_col)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                painter.drawText(int(start_x + dx), int(main_baseline + dy), text)

            # 单句播放时间进度 (0.0 -> 1.0)
            if current_line_obj:
                dur = max(1000, current_line_obj.duration_ms)
                line_r = min(1.0, max(0.0, (live_ms - current_line_obj.time_ms) / float(dur)))
            elif force_full_progress:
                line_r = 1.0
            else:
                line_r = 0.0

            # 绘制下方圆润胶囊进度条 (固定居中，不随文本偏移，可配置关闭)
            if self._show_line_progress:
                bar_w = min(220.0, max(130.0, view_w * 0.45))
                bar_h = 3.5
                bar_r = 1.75
                bar_x = (w - bar_w) / 2.0
                bar_y = base_y + total_h + 8.0

                track_rect = QRectF(bar_x, bar_y, bar_w, bar_h)
                track_path = QPainterPath()
                track_path.addRoundedRect(track_rect, bar_r, bar_r)
                painter.fillPath(track_path, QColor(255, 255, 255, int(alpha * 38)))

                fill_w = max(bar_h, bar_w * line_r)
                fill_rect = QRectF(bar_x, bar_y, fill_w, bar_h)
                fill_path = QPainterPath()
                fill_path.addRoundedRect(fill_rect, bar_r, bar_r)

                fill_grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
                fill_grad.setColorAt(0.0, QColor(255, 255, 255, int(alpha * 230)))
                fill_grad.setColorAt(1.0, QColor(160, 230, 255, int(alpha * 255)))
                painter.fillPath(fill_path, QBrush(fill_grad))

        # ── 4. 译文渲染（随主句同步平滑移动）──
        if has_trans:
            painter.setFont(self._font_sub)
            tr_w = fm_s.horizontalAdvance(trans)
            # 译文起始 X 与主句保持自然对齐或居中
            if main_w > view_w:
                tr_x = start_x
            else:
                tr_x = (w - tr_w) / 2.0
            tr_baseline = base_y + fm_m.height() + 6 + fm_s.ascent()

            ratio = min(1.0, max(0.0, (progress_x - start_x) / max(1.0, float(main_w))))
            tr_alpha = int(alpha * (100 + int(ratio * 75)))
            painter.setPen(QColor(255, 255, 255, tr_alpha))
            painter.drawText(int(tr_x), int(tr_baseline), trans)

    # ── 右下角半矩形缩放控件绘制 ─────────────────────────────────────────────
    def _draw_resize_grip(self, painter: QPainter, w: int, h: int) -> None:
        """在右下角绘制精致的半矩形折角直角手柄 (⌟)"""
        grip_x = w - 16
        grip_y = h - 16
        length = 10

        grip_alpha = int(self._opacity * (220 if self._hover_grip or self._is_resizing else 70))
        pen = QPen(QColor(255, 255, 255, grip_alpha), 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        path = QPainterPath()
        path.moveTo(grip_x - length, grip_y)
        path.lineTo(grip_x, grip_y)
        path.lineTo(grip_x, grip_y - length)
        painter.drawPath(path)

    # ── 待机极简状态 ─────────────────────────────────────────────────────────
    def _draw_standby(self, painter: QPainter, w: int, h: int) -> None:
        painter.setFont(self._font_sub)
        fm = QFontMetrics(self._font_sub)
        txt = self._status_text
        col = QColor(255, 255, 255, int(self._opacity * 80))
        painter.setPen(col)
        tx = (w - fm.horizontalAdvance(txt)) // 2
        ty = (h + fm.ascent()) // 2
        painter.drawText(tx, ty, txt)

    # ── 鼠标与拖拽调整大小交互 ───────────────────────────────────────────────
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            pos = e.position().toPoint()
            w, h = self.width(), self.height()

            if pos.x() >= w - GRIP_SIZE and pos.y() >= h - GRIP_SIZE:
                self._is_resizing = True
                self._resize_start_pos = e.globalPosition().toPoint()
                self._orig_size = self.size()
            else:
                self._is_dragging = True
                self._drag_offset = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e: QMouseEvent):
        pos = e.position().toPoint()
        w, h = self.width(), self.height()

        is_on_grip = (pos.x() >= w - GRIP_SIZE and pos.y() >= h - GRIP_SIZE)
        if is_on_grip != self._hover_grip:
            self._hover_grip = is_on_grip
            self.update()

        if self._is_resizing and self._resize_start_pos and self._orig_size:
            delta = e.globalPosition().toPoint() - self._resize_start_pos
            new_w = max(420, self._orig_size.width() + delta.x())
            new_h = max(90, self._orig_size.height() + delta.y())
            self.resize(new_w, new_h)
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif self._is_dragging and self._drag_offset and (e.buttons() == Qt.MouseButton.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag_offset)
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            if is_on_grip:
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self._is_resizing = False
            self._drag_offset = None
            self._resize_start_pos = None
            self._orig_size = None

            g = self.geometry()
            settings.set_overlay_geometry(g.x(), g.y(), g.width(), g.height())

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._ctrl.switch_mode("fullscreen")

    def wheelEvent(self, e: QWheelEvent):
        delta = e.angleDelta().y() / 1200.0
        self._opacity = max(0.2, min(1.0, self._opacity + delta))
        settings.set_opacity(self._opacity)
        self.update()

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: rgba(26, 28, 40, 0.95); color: #fff;
                    border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 10px;
                    padding: 6px; font-size: 13px; }
            QMenu::item { padding: 6px 24px; border-radius: 6px; }
            QMenu::item:selected { background: rgba(255, 255, 255, 0.15); }
        """)
        act_full = menu.addAction("🖥  沉浸全画幅模式")
        menu.addSeparator()
        label_tr = ("✓" if self._show_translation else " ") + "  显示译文"
        act_tr = menu.addAction(label_tr)
        label_pb = ("✓" if self._show_line_progress else " ") + "  非逐字进度条"
        act_pb = menu.addAction(label_pb)
        menu.addSeparator()
        act_set = menu.addAction("⚙️  设置…")
        act_quit = menu.addAction("✕  退出")

        act_full.triggered.connect(lambda: self._ctrl.switch_mode("fullscreen"))
        act_tr.triggered.connect(self._toggle_translation)
        act_pb.triggered.connect(self._toggle_line_progress)
        act_set.triggered.connect(self._ctrl.open_settings)
        act_quit.triggered.connect(QApplication.quit)
        menu.exec(e.globalPos())

    def _toggle_translation(self):
        self._show_translation = not self._show_translation
        settings.set_show_translation(self._show_translation)
        self.update()

    def _toggle_line_progress(self):
        self._show_line_progress = not self._show_line_progress
        settings.set_show_line_progress(self._show_line_progress)
        self.update()

    def keyPressEvent(self, e: QKeyEvent):
        k = e.key()
        if k == Qt.Key.Key_Left:
            self._ctrl.smtc.adjust_offset(-5000)
        elif k == Qt.Key.Key_Right:
            self._ctrl.smtc.adjust_offset(5000)
        elif k == Qt.Key.Key_F:
            self._ctrl.switch_mode("fullscreen")
        else:
            super().keyPressEvent(e)

    # ── 字体生成器与设置重载 ─────────────────────────────────────────────────
    @staticmethod
    def _create_round_font(size: int, bold: bool) -> QFont:
        return font_manager.make_app_font(size, bold=bold)

    def set_live_opacity(self, opacity: float) -> None:
        """实时响应设置面板滑动条的不透明度变化并立即重绘"""
        self._opacity = max(0.15, min(1.0, float(opacity)))
        self.update()

    def reload_settings(self):
        self._opacity = settings.get_opacity()
        self._font_size = settings.get_font_size_current()
        self._font_main = self._create_round_font(self._font_size, bold=True)
        self._font_sub = self._create_round_font(settings.get_font_size_context(), bold=False)
        self._show_translation = settings.get_show_translation()
        self._show_line_progress = settings.get_show_line_progress()
        self.update()

    def closeEvent(self, e):
        g = self.geometry()
        settings.set_overlay_geometry(g.x(), g.y(), g.width(), g.height())
        super().closeEvent(e)
