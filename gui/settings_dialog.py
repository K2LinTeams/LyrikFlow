"""
settings_dialog.py — 设置对话框
"""
from __future__ import annotations

import copy
from typing import Optional

from PyQt6.QtCore import Qt, QSize, QRectF, pyqtProperty, QPropertyAnimation, QEasingCurve, QPoint, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QFont, QImage, QPixmap, QPainterPath
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QLineEdit, QPushButton, QSpinBox, QWidget,
    QScrollArea, QStackedWidget, QFrame, QSizePolicy,
    QAbstractButton, QApplication, QGraphicsDropShadowEffect,
    QCheckBox
)

try:
    from core import settings, font_manager, db_cache, lyrics_fetcher
    from core.font_manager import FontItem
    from core.providers.base import SearchSongItem
except ImportError:
    import settings
    import font_manager
    import db_cache
    import lyrics_fetcher
    from font_manager import FontItem
    from providers.base import SearchSongItem


# ── MD3 全局样式表构建器 ──────────────────────────────────────
def build_dialog_stylesheet(font_css: str = "") -> str:
    if not font_css:
        font_css = font_manager.get_font_css_family()
    return f"""
SettingsDialog, QDialog#SettingsDialog {{
    background: transparent;
    color: #1B1F24;
    font-family: {font_css};
}}

QMessageBox {{
    background-color: #FFFFFF;
    color: #1B1F24;
    font-family: {font_css};
}}
QMessageBox QLabel {{
    background-color: transparent;
    color: #1B1F24;
    font-size: 13px;
}}
QMessageBox QPushButton {{
    background-color: #0B57D0;
    color: #FFFFFF;
    border: none;
    border-radius: 14px;
    padding: 6px 20px;
    font-family: {font_css};
    font-size: 12px;
    font-weight: 600;
    min-width: 60px;
}}
QMessageBox QPushButton:hover {{
    background-color: #0842A0;
}}

QLabel, QPushButton, QLineEdit, QSpinBox {{
    font-family: {font_css};
}}

QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}

/* 滚动条 */
QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 6px;
    margin: 4px 0 4px 0;
}}
QScrollBar::handle:vertical {{
    background: #D0DBEE;
    min-height: 24px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: #0B57D0;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* 输入框与微调框 */
QLineEdit {{
    background: #FFFFFF;
    border: 1.5px solid #DCE3EE;
    border-radius: 16px;
    color: #1B1F24;
    font-family: {font_css};
    padding: 8px 16px;
    font-size: 13px;
    selection-background-color: #D3E3FD;
    selection-color: #041E49;
}}
QLineEdit:focus {{
    border: 2px solid #0B57D0;
    background: #FFFFFF;
}}

QSpinBox {{
    background: #FFFFFF;
    border: 1.5px solid #DCE3EE;
    border-radius: 16px;
    color: #1B1F24;
    font-family: {font_css};
    padding: 6px 14px;
    font-size: 13px;
}}
QSpinBox:focus {{
    border: 2px solid #0B57D0;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 20px;
    border: none;
    background: transparent;
}}

/* 滑动条 */
QSlider::groove:horizontal {{
    height: 6px;
    background: #E1E8F5;
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: #0B57D0;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    width: 20px;
    height: 20px;
    margin: -7px 0;
    background: #0B57D0;
    border: 2.5px solid #FFFFFF;
    border-radius: 10px;
}}
QSlider::handle:horizontal:hover {{
    background: #1B6EF3;
    border-color: #FFFFFF;
}}

/* 通用按钮基类规范 */
QPushButton {{
    border-radius: 18px;
    font-family: {font_css};
    font-size: 13px;
    border: none;
    outline: none;
}}
"""


def apply_pill_primary(btn: QPushButton, font_css: str = ""):
    if not font_css:
        font_css = font_manager.get_font_css_family()
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: #0B57D0;
            color: #FFFFFF;
            border: none;
            border-radius: 19px;
            padding: 8px 24px;
            font-family: {font_css};
            font-size: 13px;
            font-weight: 600;
            outline: none;
        }}
        QPushButton:hover {{
            background-color: #1B6EF3;
        }}
        QPushButton:pressed {{
            background-color: #0842A0;
        }}
    """)


def apply_pill_tonal(btn: QPushButton, font_css: str = ""):
    if not font_css:
        font_css = font_manager.get_font_css_family()
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: #EDF2FA;
            color: #1B1F24;
            border: 1px solid #DCE3EE;
            border-radius: 19px;
            padding: 8px 22px;
            font-family: {font_css};
            font-size: 13px;
            font-weight: 500;
            outline: none;
        }}
        QPushButton:hover {{
            background-color: #E2E8F4;
            color: #0B57D0;
            border-color: #B5D2FD;
        }}
        QPushButton:pressed {{
            background-color: #C2D7FC;
        }}
    """)


def apply_pill_outlined(btn: QPushButton, font_css: str = ""):
    if not font_css:
        font_css = font_manager.get_font_css_family()
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: #FFFFFF;
            color: #0B57D0;
            border: 1.5px solid #0B57D0;
            border-radius: 19px;
            padding: 8px 22px;
            font-family: {font_css};
            font-size: 13px;
            font-weight: 600;
            outline: none;
        }}
        QPushButton:hover {{
            background-color: #EDF4FE;
            border-color: #1B6EF3;
        }}
        QPushButton:pressed {{
            background-color: #D3E3FD;
        }}
    """)


def apply_circle_btn(btn: QPushButton, size: int = 32, font_css: str = ""):
    if not font_css:
        font_css = font_manager.get_font_css_family()
    radius = size // 2
    btn.setFixedSize(size, size)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: #EDF2FA;
            color: #041E49;
            border: none;
            border-radius: {radius}px;
            font-family: {font_css};
            font-size: 13px;
            font-weight: bold;
            outline: none;
            padding: 0px;
        }}
        QPushButton:hover {{
            background-color: #D3E3FD;
            color: #0B57D0;
        }}
        QPushButton:pressed {{
            background-color: #C2D7FC;
        }}
        QPushButton:disabled {{
            background-color: #F5F7FA;
            color: #C4C7C5;
        }}
    """)


def apply_chip(btn: QPushButton, font_css: str = ""):
    if not font_css:
        font_css = font_manager.get_font_css_family()
    btn.setFixedHeight(28)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: #F0F4FA;
            color: #475467;
            border: 1px solid #DCE3EE;
            border-radius: 14px;
            padding: 2px 12px;
            font-family: {font_css};
            font-size: 12px;
            font-weight: 500;
            outline: none;
        }}
        QPushButton:hover {{
            background-color: #D3E3FD;
            color: #0B57D0;
            border-color: #B5D2FD;
        }}
        QPushButton:pressed {{
            background-color: #C2D7FC;
        }}
    """)


def apply_pill_banner_btn(btn: QPushButton, font_css: str = ""):
    if not font_css:
        font_css = font_manager.get_font_css_family()
    btn.setFixedHeight(34)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: #FFFFFF;
            color: #041E49;
            border: 1px solid #C6D8F8;
            border-radius: 17px;
            padding: 6px 16px;
            font-family: {font_css};
            font-size: 12px;
            font-weight: 600;
            outline: none;
        }}
        QPushButton:hover {{
            background-color: #F2F7FF;
            color: #0B57D0;
            border-color: #0B57D0;
        }}
        QPushButton:pressed {{
            background-color: #D3E3FD;
        }}
    """)


def apply_chip_active(btn: QPushButton, font_css: str = ""):
    if not font_css:
        font_css = font_manager.get_font_css_family()
    btn.setFixedHeight(28)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: #0B57D0;
            color: #FFFFFF;
            border: 1px solid #0B57D0;
            border-radius: 14px;
            padding: 2px 12px;
            font-family: {font_css};
            font-size: 12px;
            font-weight: 600;
            outline: none;
        }}
    """)


class SearchVersionWorker(QThread):
    results_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, keyword: str, provider_filter: str = "all", parent=None):
        super().__init__(parent)
        self.keyword = keyword
        self.provider_filter = provider_filter

    def run(self):
        try:
            results = lyrics_fetcher.search_all_sources(self.keyword, "", provider_filter=self.provider_filter, limit=12)
            self.results_ready.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))


class ApplyVersionWorker(QThread):
    apply_finished = pyqtSignal(bool, str, object)

    def __init__(self, title: str, artist: str, item: SearchSongItem, parent=None):
        super().__init__(parent)
        self.title = title
        self.artist = artist
        self.item = item

    def run(self):
        try:
            parsed, cover, sub_name = lyrics_fetcher.fetch_and_apply_override(self.title, self.artist, self.item)
            if parsed:
                self.apply_finished.emit(True, "应用成功", parsed)
            else:
                self.apply_finished.emit(False, "未能获取到该版本的歌词", None)
        except Exception as e:
            self.apply_finished.emit(False, str(e), None)


# ── MD3 颜色插值辅助 ──────────────────────────────────────────
def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, float(t)))
    r = int(c1.red() + (c2.red() - c1.red()) * t)
    g = int(c1.green() + (c2.green() - c1.green()) * t)
    b = int(c1.blue() + (c2.blue() - c1.blue()) * t)
    return QColor(r, g, b)


# ── MD3 规范圆润开关控件 ──────────────────────────────────────
class MD3Switch(QAbstractButton):
    """
    Material Design 3 原生风格胶囊开关
    - 开启：高对比度 Google 蓝轨道 + 纯白圆形滑块
    - 关闭：柔和浅灰蓝轨道 + 深灰蓝圆形滑块
    - 联动平滑缓动动画与渐变色插值，避免残影与点击不同步
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(50, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._thumb_pos = 1.0 if self.isChecked() else 0.0
        self._anim = QPropertyAnimation(self, b"thumb_pos", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.toggled.connect(self._on_toggled)

    def sizeHint(self) -> QSize:
        return QSize(50, 28)

    @pyqtProperty(float)
    def thumb_pos(self) -> float:
        return self._thumb_pos

    @thumb_pos.setter
    def thumb_pos(self, pos: float):
        self._thumb_pos = pos
        if self.parentWidget():
            self.parentWidget().update(self.geometry())
        else:
            self.update()

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._thumb_pos = 1.0 if checked else 0.0
        if self.parentWidget():
            self.parentWidget().update(self.geometry())
        else:
            self.update()

    def _on_toggled(self, checked: bool):
        if self.isVisible():
            self._anim.stop()
            self._anim.setStartValue(self._thumb_pos)
            self._anim.setEndValue(1.0 if checked else 0.0)
            self._anim.start()
        else:
            self._thumb_pos = 1.0 if checked else 0.0
            if self.parentWidget():
                self.parentWidget().update(self.geometry())
            else:
                self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        track_w = 46.0
        track_h = 24.0
        x_offset = (w - track_w) / 2.0
        y_offset = (h - track_h) / 2.0
        track_rect = QRectF(x_offset, y_offset, track_w, track_h)

        t = self._thumb_pos
        if self.isEnabled():
            track_color = _lerp_color(QColor("#E3E8F0"), QColor("#0B57D0"), t)
            thumb_color = _lerp_color(QColor("#5A6A80"), QColor("#FFFFFF"), t)
            border_color = _lerp_color(QColor("#C4D0E3"), QColor("#0B57D0"), t)
        else:
            track_color = QColor("#EDF0F5")
            thumb_color = QColor("#B5BCC8")
            border_color = QColor("#DCE2EC")

        # 绘制药丸跑道外轨
        painter.setPen(QPen(border_color, 1.2))
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, 12.0, 12.0)

        # 圆形滑块插值位置
        start_x = track_rect.left() + 2.5
        end_x = track_rect.right() - 21.5
        cur_x = start_x + (end_x - start_x) * t
        cur_y = track_rect.top() + 2.5
        thumb_rect = QRectF(cur_x, cur_y, 19.0, 19.0)

        # 绘制纯圆滑块
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(thumb_color)
        painter.drawEllipse(thumb_rect)


# ── MD3 卡片容器辅助构建 ──────────────────────────────────────────────────────
class MD3Card(QFrame):
    def __init__(self, parent=None, bg="#FFFFFF", border="#E1E8F5", radius=18):
        super().__init__(parent)
        self.setStyleSheet(
            f"MD3Card {{ background: {bg}; border: 1.5px solid {border}; border-radius: {radius}px; }}"
        )


class CoverThumbnailWidget(QWidget):
    """歌曲封面缩略图控件"""
    def __init__(self, thumb_bytes: Optional[bytes] = None, size: int = 50, parent=None):
        super().__init__(parent)
        self._size = size
        self._pixmap: Optional[QPixmap] = None
        self.setFixedSize(size + 10, size + 10)
        if thumb_bytes:
            img = QImage.fromData(bytes(thumb_bytes))
            if not img.isNull():
                self._pixmap = QPixmap.fromImage(img)

    def set_cover(self, thumb_bytes: Optional[bytes]):
        if thumb_bytes:
            img = QImage.fromData(bytes(thumb_bytes))
            if not img.isNull():
                self._pixmap = QPixmap.fromImage(img)
            else:
                self._pixmap = None
        else:
            self._pixmap = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        margin = 5.0
        s = float(self._size)
        cover_rect = QRectF(margin, margin, s, s)
        radius = 12.0

        if self._pixmap and not self._pixmap.isNull():
            # 1. 底层环境光晕
            glow_rect = cover_rect.adjusted(-4, -4, 4, 4)
            glow_pix = self._pixmap.scaled(
                16, 16,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ).scaled(
                int(glow_rect.width()), int(glow_rect.height()),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            glow_path = QPainterPath()
            glow_path.addRoundedRect(glow_rect, radius + 3.0, radius + 3.0)
            painter.save()
            painter.setClipPath(glow_path)
            painter.setOpacity(0.35)
            painter.drawPixmap(int(glow_rect.x()), int(glow_rect.y()), glow_pix)
            painter.restore()

            # 2. 封面圆角裁切
            path = QPainterPath()
            path.addRoundedRect(cover_rect, radius, radius)
            painter.save()
            painter.setClipPath(path)
            scaled = self._pixmap.scaled(
                int(s * 2), int(s * 2),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(cover_rect.toRect(), scaled)
            painter.restore()

            # 3. 边框
            painter.save()
            inner_pen = QPen(QColor(255, 255, 255, 220), 1.5)
            painter.setPen(inner_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(cover_rect, radius, radius)

            outer_pen = QPen(QColor(180, 200, 230, 90), 1.0)
            painter.setPen(outer_pen)
            painter.drawRoundedRect(cover_rect.adjusted(-0.5, -0.5, 0.5, 0.5), radius + 0.5, radius + 0.5)
            painter.restore()

        else:
            # 待机占位图
            bg_path = QPainterPath()
            bg_path.addRoundedRect(cover_rect, radius, radius)
            painter.fillPath(bg_path, QColor(228, 238, 252))

            border_pen = QPen(QColor(198, 216, 248), 1.5)
            painter.setPen(border_pen)
            painter.drawRoundedRect(cover_rect, radius, radius)

            painter.setPen(QColor(11, 87, 208))
            f = QFont("Segoe UI Symbol", 18, QFont.Weight.Bold)
            painter.setFont(f)
            painter.drawText(cover_rect, int(Qt.AlignmentFlag.AlignCenter), "♫")


# ── 主设置对话框 ──────────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    def __init__(
        self,
        parent=None,
        controller=None,
        overlay_widget=None,
        current_title: str = "",
        current_artist: str = "",
        thumb_bytes: Optional[bytes] = None,
    ):
        super().__init__(parent)
        self.setObjectName("SettingsDialog")
        self.setWindowTitle("LyrikFlow — 设置与偏好")
        self._controller = controller
        self._overlay_widget = overlay_widget
        self._current_title = (current_title or "").strip()
        self._current_artist = (current_artist or "").strip()
        self._thumb_bytes = thumb_bytes
        if not self._thumb_bytes and self._current_title:
            cached = db_cache.get_song_cache(self._current_title, self._current_artist)
            if cached and cached.get("hd_cover"):
                self._thumb_bytes = cached["hd_cover"]
        self._song_offsets_draft: dict[str, int] = dict(db_cache.get_all_song_offsets())
        self._initial_opacity = settings.get_opacity()
        self._initial_offset = settings.get_effective_song_offset(self._current_title, self._current_artist)

        # 移除系统原生标题栏与冗余窗口控件，呈现现代无边框圆角卡片
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(720, 700)
        self.setMinimumSize(660, 600)

        self._has_centered = False
        self._drag_pos: Optional[QPoint] = None

        # 内存中暂存的字体配置项副本，支持上移/下移/停用/取消回滚
        self._font_items: list[FontItem] = copy.deepcopy(font_manager.get_font_items())

        # 动态应用当前自定义字体族栈
        font_css = font_manager.get_font_css_family(self._font_items)
        self.setStyleSheet(build_dialog_stylesheet(font_css))
        self.setFont(font_manager.make_app_font(13))

        # 歌词源指定与版本搜索状态
        self._all_search_results: list[SearchSongItem] = []
        self._all_search_kw: str = ""
        self._displayed_search_results: list[SearchSongItem] = []
        self._last_search_results: list[SearchSongItem] = []
        self._active_applied_item: Optional[SearchSongItem] = None
        self._search_worker: Optional[SearchVersionWorker] = None
        self._apply_worker: Optional[ApplyVersionWorker] = None
        self._override_provider_filter: str = "all"
        self._provider_chips: dict[str, QPushButton] = {}

        self._build_ui()

    def reject(self):
        # 取消时还原悬浮窗实时不透明度与初始偏移量
        if self._overlay_widget:
            self._overlay_widget.set_live_opacity(self._initial_opacity)
        if self._controller:
            self._controller.preview_offset(self._initial_offset)
        super().reject()

    def _center_on_screen(self):
        """将窗口水平、垂直双向居中于当前屏幕中央"""
        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._has_centered:
            self._center_on_screen()
            self._has_centered = True

    # ── 标题栏按住拖拽移动窗口 ─────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 顶部 Header 区域支持鼠标拖拽移动无边框窗口
            if event.pos().y() <= 90:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def _build_ui(self):
        # 1. 外层布局：为阴影预留出血边缘
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(14, 14, 14, 14)
        outer_layout.setSpacing(0)

        # 2. 核心主卡片背景
        self._main_card = QFrame(self)
        self._main_card.setObjectName("main_card")
        self._main_card.setStyleSheet("""
            #main_card {
                background-color: #F8FAFD;
                border: 1.5px solid #D8E2F0;
                border-radius: 20px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self._main_card)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 6)
        self._main_card.setGraphicsEffect(shadow)

        outer_layout.addWidget(self._main_card)

        # 3. 内部主布局
        root = QVBoxLayout(self._main_card)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # 顶部 Header
        header = QHBoxLayout()
        header.setSpacing(14)

        # 蓝白圆角图标微标
        icon_badge = QLabel("♫")
        icon_badge.setFixedSize(40, 40)
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_badge.setStyleSheet(
            "background: #D3E3FD; color: #0B57D0; border-radius: 20px; font-size: 20px; font-weight: bold;"
        )
        header.addWidget(icon_badge)

        v_titles = QVBoxLayout()
        v_titles.setSpacing(2)
        lbl_title = QLabel("设置")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #1B1F24;")
        lbl_sub = QLabel("外观与播放设置")
        lbl_sub.setStyleSheet("font-size: 12px; color: #535F70;")
        v_titles.addWidget(lbl_title)
        v_titles.addWidget(lbl_sub)
        header.addLayout(v_titles)
        header.addStretch()

        btn_close = QPushButton("✕")
        apply_circle_btn(btn_close, 32)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        header.addWidget(btn_close)

        root.addLayout(header)

        # MD3 分段导航药丸胶囊栏
        nav_container = QFrame()
        nav_container.setStyleSheet(
            "background: #EDF2FA; border-radius: 22px; padding: 3px;"
        )
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(4, 4, 4, 4)
        nav_layout.setSpacing(6)

        self._btn_tab_font = QPushButton("字体设置")
        self._btn_tab_ui   = QPushButton("歌词显示")
        self._btn_tab_smtc = QPushButton("播放与同步")

        self._nav_buttons = [self._btn_tab_font, self._btn_tab_ui, self._btn_tab_smtc]
        for i, b in enumerate(self._nav_buttons):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(36)
            b.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
            nav_layout.addWidget(b)

        root.addWidget(nav_container)

        # 多页内容容器
        self._stack = QStackedWidget()
        self._stack.addWidget(self._create_font_page())
        self._stack.addWidget(self._make_scrollable(self._create_ui_page()))
        self._stack.addWidget(self._make_scrollable(self._create_smtc_page()))
        root.addWidget(self._stack, 1)

        # 底部动作栏
        footer = QHBoxLayout()
        footer.setSpacing(12)

        font_css = font_manager.get_font_css_family(self._font_items)

        self._btn_reset = QPushButton("恢复默认")
        apply_pill_outlined(self._btn_reset, font_css)
        self._btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_reset.setFixedHeight(38)
        self._btn_reset.clicked.connect(self._reset_defaults)
        footer.addWidget(self._btn_reset)

        footer.addStretch()

        self._btn_cancel = QPushButton("取消")
        apply_pill_tonal(self._btn_cancel, font_css)
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel.setFixedHeight(38)
        self._btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self._btn_cancel)

        self._btn_save = QPushButton("保存并应用")
        apply_pill_primary(self._btn_save, font_css)
        self._btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save.setFixedHeight(38)
        self._btn_save.clicked.connect(self._save_and_apply)
        footer.addWidget(self._btn_save)

        root.addLayout(footer)

        # 初始化激活第 1 个 Tab
        self._switch_tab(0)

    # ── 导航切换 ─────────────────────────────────────────────────────────────
    def _switch_tab(self, idx: int):
        self._stack.setCurrentIndex(idx)
        w = self._stack.widget(idx)
        if isinstance(w, QScrollArea):
            w.verticalScrollBar().setValue(0)
        font_css = font_manager.get_font_css_family(self._font_items)
        for i, b in enumerate(self._nav_buttons):
            if i == idx:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #0B57D0;
                        color: #FFFFFF;
                        border-radius: 18px;
                        font-family: {font_css};
                        font-weight: 600;
                        font-size: 13px;
                        border: none;
                        padding: 0 16px;
                    }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: #475467;
                        border-radius: 18px;
                        font-family: {font_css};
                        font-weight: 500;
                        font-size: 13px;
                        border: none;
                        padding: 0 16px;
                    }}
                    QPushButton:hover {{
                        background-color: #DFE7F5;
                        color: #0B57D0;
                    }}
                """)

    def _refresh_dialog_fonts(self):
        """当字体优先级/启用状态在面板中被操作时，即时同步刷新全局与按钮控件的字体"""
        font_css = font_manager.get_font_css_family(self._font_items)
        self.setStyleSheet(build_dialog_stylesheet(font_css))
        self.setFont(font_manager.make_app_font(13, families=[it.family for it in self._font_items if it.enabled and it.is_valid] + font_manager.SYSTEM_FALLBACK_FAMILIES))
        # 刷新三卡切换按钮
        self._switch_tab(self._stack.currentIndex())
        # 刷新底部按钮
        if hasattr(self, "_btn_reset"):
            apply_pill_outlined(self._btn_reset, font_css)
        if hasattr(self, "_btn_cancel"):
            apply_pill_tonal(self._btn_cancel, font_css)
        if hasattr(self, "_btn_save"):
            apply_pill_primary(self._btn_save, font_css)
        if hasattr(self, "_btn_folder"):
            apply_pill_banner_btn(self._btn_folder, font_css)
        if hasattr(self, "_btn_rescan"):
            apply_pill_banner_btn(self._btn_rescan, font_css)
        # 刷新歌词展示窗
        if hasattr(self, "_lbl_prev_cur"):
            if hasattr(self, "_set_font_mode"):
                self._set_font_mode(getattr(self, "_font_mode", "overlay"))
            else:
                self._update_ui_preview()

    def _make_scrollable(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(widget)
        return scroll

    # ── 字体管理设置 ─────────────────────────────────────────────────────────
    def _create_font_page(self) -> QWidget:
        page = QWidget()
        l = QVBoxLayout(page)
        l.setContentsMargins(0, 4, 0, 0)
        l.setSpacing(12)

        # 说明与操作工具条卡片
        banner = MD3Card(bg="#EDF2FA", border="#D3E3FD", radius=16)
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(14, 10, 14, 10)
        bl.setSpacing(10)

        info_v = QVBoxLayout()
        info_v.setSpacing(2)
        info_title = QLabel("本地字体")
        info_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #041E49;")
        info_desc = QLabel(
            "按顺序优先使用字体。若某个字形缺失，会自动回退至后续启用的字体及系统字体。"
        )
        info_desc.setStyleSheet("font-size: 11px; color: #475467;")
        info_desc.setWordWrap(True)
        info_v.addWidget(info_title)
        info_v.addWidget(info_desc)
        bl.addLayout(info_v, 1)

        font_css = font_manager.get_font_css_family(self._font_items)

        self._btn_folder = QPushButton("📁 打开字体文件夹")
        apply_pill_banner_btn(self._btn_folder, font_css)
        self._btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_folder.clicked.connect(font_manager.open_fonts_folder)
        bl.addWidget(self._btn_folder)

        self._btn_rescan = QPushButton("🔄 重新扫描")
        apply_pill_banner_btn(self._btn_rescan, font_css)
        self._btn_rescan.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_rescan.clicked.connect(self._rescan_fonts)
        bl.addWidget(self._btn_rescan)

        l.addWidget(banner)

        # 滚动字体卡片列表
        self._font_scroll = QScrollArea()
        self._font_scroll.setWidgetResizable(True)
        self._font_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._font_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._font_list_container = QWidget()
        self._font_list_layout = QVBoxLayout(self._font_list_container)
        self._font_list_layout.setContentsMargins(0, 0, 6, 0)
        self._font_list_layout.setSpacing(10)

        self._render_font_items()

        self._font_scroll.setWidget(self._font_list_container)
        l.addWidget(self._font_scroll, 1)

        return page

    def _render_font_items(self):
        """重新渲染字体卡片列表"""
        # 清空原有的子控件
        while self._font_list_layout.count():
            item = self._font_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._font_items:
            empty_lbl = QLabel("data/fonts/ 目录下暂未扫描到字体文件。\n可将 .ttf / .otf 字体文件复制至 data/fonts 目录后点击重新扫描。")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet("color: #72777A; padding: 40px; font-size: 13px;")
            self._font_list_layout.addWidget(empty_lbl)
            self._font_list_layout.addStretch()
            return

        for index, item in enumerate(self._font_items):
            card = self._create_single_font_card(index, item)
            self._font_list_layout.addWidget(card)

        self._font_list_layout.addStretch()

    def _create_single_font_card(self, index: int, item: FontItem) -> QWidget:
        card = MD3Card(
            bg="#FFFFFF" if item.enabled else "#F6F8FB",
            border="#C6D8F8" if item.enabled else "#E1E8F5",
            radius=16,
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 12, 14, 12)
        cl.setSpacing(8)

        # 头部：序号徽章、家族名、状态微标、上移/下移/开关
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        # 圆形序号徽标
        badge = QLabel(f"#{index + 1}" if item.enabled else "关")
        badge.setFixedSize(38, 26)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if item.enabled:
            badge.setStyleSheet(
                "background: #D3E3FD; color: #041E49; border-radius: 13px; font-weight: bold; font-size: 12px;"
            )
        else:
            badge.setStyleSheet(
                "background: #ECEFF4; color: #8C939E; border-radius: 13px; font-weight: normal; font-size: 11px;"
            )
        row1.addWidget(badge)

        # 字体家族名
        name_v = QVBoxLayout()
        name_v.setSpacing(2)
        lbl_family = QLabel(item.family)
        lbl_family.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {'#1B1F24' if item.enabled else '#8C939E'};"
        )
        name_v.addWidget(lbl_family)

        # 文件详情
        if item.is_valid:
            files_str = ", ".join(item.files) if item.files else "系统内置字体"
            size_str = font_manager.format_bytes(item.total_size)
            details_text = f"{files_str} · {size_str}"
        else:
            details_text = f"{item.error_msg or '加载失败'}"

        lbl_details = QLabel(details_text)
        lbl_details.setStyleSheet(
            f"font-size: 11px; color: {'#535F70' if item.is_valid else '#B3261E'};"
        )
        name_v.addWidget(lbl_details)
        row1.addLayout(name_v, 1)

        # 状态徽章
        status_lbl = QLabel()
        if not item.is_valid:
            status_lbl.setText("缺失")
            status_lbl.setStyleSheet(
                "background: #FCE8E6; color: #B3261E; border-radius: 10px; padding: 2px 8px; font-size: 11px; font-weight: bold;"
            )
        elif item.enabled:
            status_lbl.setText("已启用")
            status_lbl.setStyleSheet(
                "background: #E6F4EA; color: #137333; border-radius: 10px; padding: 2px 8px; font-size: 11px; font-weight: bold;"
            )
        else:
            status_lbl.setText("未启用")
            status_lbl.setStyleSheet(
                "background: #F1F3F4; color: #5F6368; border-radius: 10px; padding: 2px 8px; font-size: 11px;"
            )
        row1.addWidget(status_lbl)

        # 上移按钮
        btn_up = QPushButton("▲")
        apply_circle_btn(btn_up, 30)
        btn_up.setToolTip("提高优先级 (上移)")
        btn_up.setEnabled(index > 0)
        btn_up.clicked.connect(lambda _, i=index: self._move_font(i, -1))
        row1.addWidget(btn_up)

        # 下移按钮
        btn_down = QPushButton("▼")
        apply_circle_btn(btn_down, 30)
        btn_down.setToolTip("降低优先级 (下移)")
        btn_down.setEnabled(index < len(self._font_items) - 1)
        btn_down.clicked.connect(lambda _, i=index: self._move_font(i, 1))
        row1.addWidget(btn_down)

        # 启用开关
        switch = MD3Switch()
        switch.setChecked(item.enabled)
        switch.setToolTip("启用/停用该字体")
        switch.toggled.connect(lambda checked, it=item: self._on_font_toggled(it, checked))
        row1.addWidget(switch)

        cl.addLayout(row1)

        # 实时字体预览栏
        preview_box = QFrame()
        preview_box.setStyleSheet(
            f"background: {'#F8FAFD' if item.enabled else '#F0F3F7'}; "
            f"border: 1px solid {'#D9E2F2' if item.enabled else '#E3E7EE'}; "
            "border-radius: 12px; padding: 6px 14px;"
        )
        pl = QHBoxLayout(preview_box)
        pl.setContentsMargins(6, 4, 6, 4)

        sample_text = font_manager.get_font_sample_text(item.family)
        lbl_preview = QLabel(sample_text)
        lbl_preview.setObjectName("single_font_preview")
        lbl_preview.setStyleSheet(f"""
            QLabel#single_font_preview {{
                font-family: "{item.family}";
                font-size: 13px;
                color: {'#1B1F24' if item.enabled else '#8C939E'};
                background: transparent;
                border: none;
            }}
        """)
        custom_font = QFont(item.family, 13)
        custom_font.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
        custom_font.setWeight(QFont.Weight.Medium)
        lbl_preview.setFont(custom_font)
        pl.addWidget(lbl_preview)

        cl.addWidget(preview_box)
        return card

    def _move_font(self, index: int, delta: int):
        target = index + delta
        if 0 <= target < len(self._font_items):
            self._font_items[index], self._font_items[target] = self._font_items[target], self._font_items[index]
            self._render_font_items()
            self._refresh_dialog_fonts()

    def _on_font_toggled(self, item: FontItem, checked: bool):
        item.enabled = checked
        self._render_font_items()
        self._refresh_dialog_fonts()

    def _rescan_fonts(self):
        # 重新扫描磁盘并与当前内存中设置同步
        scanned = font_manager.scan_fonts()
        # 更新 self._font_items
        self._font_items = copy.deepcopy(scanned)
        self._render_font_items()
        self._refresh_dialog_fonts()

    # ── TAB 2: 歌词与界面设置 ─────────────────────────────────────────────────
    def _create_ui_page(self) -> QWidget:
        page = QWidget()
        l = QVBoxLayout(page)
        l.setContentsMargins(0, 4, 0, 0)
        l.setSpacing(12)

        # 1. 单曲歌词源与版本指定卡片
        card_override = self._create_lyric_override_card()
        l.addWidget(card_override)

        # 2. 悬浮条背景不透明度卡片
        card_op = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
        ol = QVBoxLayout(card_op)
        ol.setContentsMargins(18, 14, 18, 14)
        ol.setSpacing(10)

        top_op = QHBoxLayout()
        lbl_op_title = QLabel("悬浮窗背景透明度")
        lbl_op_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
        top_op.addWidget(lbl_op_title)
        top_op.addStretch()

        self._lbl_op_val = QLabel(f"{int(settings.get_opacity() * 100)}%")
        self._lbl_op_val.setStyleSheet(
            "background: #D3E3FD; color: #041E49; border-radius: 12px; padding: 2px 10px; font-weight: bold; font-size: 12px;"
        )
        top_op.addWidget(self._lbl_op_val)
        ol.addLayout(top_op)

        self._slider_op = QSlider(Qt.Orientation.Horizontal)
        self._slider_op.setRange(15, 100)
        self._slider_op.setValue(int(settings.get_opacity() * 100))
        self._slider_op.valueChanged.connect(self._on_opacity_slider_changed)
        ol.addWidget(self._slider_op)

        # 快捷药丸按钮
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(8)
        chips_layout.addWidget(QLabel("快捷预设：", styleSheet="font-size: 11px; color: #6E7781;"))
        for percent, text in [(30, "30%"), (60, "60%"), (85, "85%"), (100, "100%")]:
            btn = QPushButton(text)
            apply_chip(btn)
            btn.clicked.connect(lambda _, v=percent: self._slider_op.setValue(v))
            chips_layout.addWidget(btn)
        chips_layout.addStretch()
        ol.addLayout(chips_layout)

        l.addWidget(card_op)

        # 2. 歌词排印与字号卡片
        card_font = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
        fl = QVBoxLayout(card_font)
        fl.setContentsMargins(18, 14, 18, 14)
        fl.setSpacing(10)

        # 头部：标题与模式切换胶囊
        top_font_h = QHBoxLayout()
        lbl_font_title = QLabel("歌词字号设置")
        lbl_font_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
        top_font_h.addWidget(lbl_font_title)
        top_font_h.addStretch()

        capsule_mode = QFrame()
        capsule_mode.setStyleSheet("background: #EDF2FA; border-radius: 15px; padding: 2px;")
        cap_l = QHBoxLayout(capsule_mode)
        cap_l.setContentsMargins(2, 2, 2, 2)
        cap_l.setSpacing(4)

        self._btn_mode_ov = QPushButton("桌面悬浮窗")
        self._btn_mode_fs = QPushButton("全屏画幅")
        for b in (self._btn_mode_ov, self._btn_mode_fs):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(26)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._btn_mode_ov.clicked.connect(lambda: self._set_font_mode("overlay"))
        self._btn_mode_fs.clicked.connect(lambda: self._set_font_mode("fullscreen"))
        cap_l.addWidget(self._btn_mode_ov)
        cap_l.addWidget(self._btn_mode_fs)
        top_font_h.addWidget(capsule_mode)
        fl.addLayout(top_font_h)

        # ── 悬浮窗面板 ──
        self._panel_ov = QWidget()
        ov_l = QVBoxLayout(self._panel_ov)
        ov_l.setContentsMargins(0, 2, 0, 2)
        ov_l.setSpacing(8)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("当前行 (px)：", styleSheet="color: #1B1F24; font-size: 13px;"))
        self._spin_cur = QSpinBox()
        self._spin_cur.setRange(16, 52)
        self._spin_cur.setValue(settings.get_font_size_current())
        self._spin_cur.wheelEvent = lambda e: e.ignore()
        self._spin_cur.valueChanged.connect(lambda _: self._update_ui_preview())
        r1.addWidget(self._spin_cur)
        r1.addSpacing(10)
        for sz in [24, 28, 32, 36]:
            btn = QPushButton(f"{sz}px")
            apply_chip(btn)
            btn.clicked.connect(lambda _, s=sz: self._spin_cur.setValue(s))
            r1.addWidget(btn)
        r1.addStretch()
        ov_l.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("译文/副行 (px)：", styleSheet="color: #1B1F24; font-size: 13px;"))
        self._spin_ctx = QSpinBox()
        self._spin_ctx.setRange(10, 32)
        self._spin_ctx.setValue(settings.get_font_size_context())
        self._spin_ctx.wheelEvent = lambda e: e.ignore()
        self._spin_ctx.valueChanged.connect(lambda _: self._update_ui_preview())
        r2.addWidget(self._spin_ctx)
        r2.addSpacing(10)
        for sz in [12, 14, 16, 18]:
            btn = QPushButton(f"{sz}px")
            apply_chip(btn)
            btn.clicked.connect(lambda _, s=sz: self._spin_ctx.setValue(s))
            r2.addWidget(btn)
        r2.addStretch()
        ov_l.addLayout(r2)
        fl.addWidget(self._panel_ov)

        # ── 全屏面板 ──
        self._panel_fs = QWidget()
        fs_panel_l = QVBoxLayout(self._panel_fs)
        fs_panel_l.setContentsMargins(0, 2, 0, 2)
        fs_panel_l.setSpacing(8)

        r_fs1 = QHBoxLayout()
        r_fs1.addWidget(QLabel("当前行 (px)：", styleSheet="color: #1B1F24; font-size: 13px;"))
        self._spin_fs_cur = QSpinBox()
        self._spin_fs_cur.setRange(16, 72)
        self._spin_fs_cur.setValue(settings.get_fullscreen_font_size_current())
        self._spin_fs_cur.wheelEvent = lambda e: e.ignore()
        self._spin_fs_cur.valueChanged.connect(lambda _: self._update_ui_preview())
        r_fs1.addWidget(self._spin_fs_cur)
        r_fs1.addSpacing(10)
        for sz in [28, 36, 42, 48]:
            btn = QPushButton(f"{sz}px")
            apply_chip(btn)
            btn.clicked.connect(lambda _, s=sz: self._spin_fs_cur.setValue(s))
            r_fs1.addWidget(btn)
        r_fs1.addStretch()
        fs_panel_l.addLayout(r_fs1)

        r_fs2 = QHBoxLayout()
        r_fs2.addWidget(QLabel("上下文行 (px)：", styleSheet="color: #1B1F24; font-size: 13px;"))
        self._spin_fs_ctx = QSpinBox()
        self._spin_fs_ctx.setRange(10, 48)
        self._spin_fs_ctx.setValue(settings.get_fullscreen_font_size_context())
        self._spin_fs_ctx.wheelEvent = lambda e: e.ignore()
        self._spin_fs_ctx.valueChanged.connect(lambda _: self._update_ui_preview())
        r_fs2.addWidget(self._spin_fs_ctx)
        r_fs2.addSpacing(10)
        for sz in [14, 16, 18, 22]:
            btn = QPushButton(f"{sz}px")
            apply_chip(btn)
            btn.clicked.connect(lambda _, s=sz: self._spin_fs_ctx.setValue(s))
            r_fs2.addWidget(btn)
        r_fs2.addStretch()
        fs_panel_l.addLayout(r_fs2)
        fl.addWidget(self._panel_fs)

        # 实时字号排版预览卡片
        self._preview_card = QFrame()
        self._preview_card.setObjectName("preview_card")
        self._preview_card.setMinimumHeight(125)
        self._preview_card.setStyleSheet("""
            #preview_card {
                background-color: #141724;
                border: 1.5px solid #282D42;
                border-radius: 14px;
            }
        """)
        prev_layout = QVBoxLayout(self._preview_card)
        prev_layout.setContentsMargins(18, 14, 18, 14)
        prev_layout.setSpacing(8)

        self._lbl_prev_cur = QLabel("不可解で不完全な魔法")
        self._lbl_prev_cur.setStyleSheet("background: transparent; border: none; color: #FFFFFF; font-weight: bold;")
        self._lbl_prev_cur.setWordWrap(True)

        self._lbl_prev_roma = QLabel("fu ka kai na, fu kan zen na ma hou")
        self._lbl_prev_roma.setStyleSheet("background: transparent; border: none; color: #A0D8EF;")
        self._lbl_prev_roma.setWordWrap(True)

        self._lbl_prev_trans = QLabel("不可解的、不完全的魔法")
        self._lbl_prev_trans.setStyleSheet("background: transparent; border: none; color: #82B1FF;")
        self._lbl_prev_trans.setWordWrap(True)

        prev_layout.addWidget(self._lbl_prev_cur)
        prev_layout.addWidget(self._lbl_prev_roma)
        prev_layout.addWidget(self._lbl_prev_trans)
        fl.addWidget(self._preview_card)

        self._set_font_mode("overlay")
        l.addWidget(card_font)

        # 3. 功能开关卡片：双语翻译
        card_trans = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
        trans_l = QHBoxLayout(card_trans)
        trans_l.setContentsMargins(18, 14, 18, 14)

        trans_v = QVBoxLayout()
        trans_v.setSpacing(2)
        lbl_trans_t = QLabel("显示双语翻译")
        lbl_trans_t.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
        lbl_trans_d = QLabel("若歌曲包含译文则同步显示")
        lbl_trans_d.setStyleSheet("font-size: 11px; color: #6E7781;")
        lbl_trans_d.setWordWrap(True)
        trans_v.addWidget(lbl_trans_t)
        trans_v.addWidget(lbl_trans_d)
        trans_l.addLayout(trans_v, 1)

        self._switch_trans = MD3Switch()
        self._switch_trans.setChecked(settings.get_show_translation())
        self._lbl_prev_trans.setVisible(settings.get_show_translation())
        self._switch_trans.toggled.connect(
            lambda checked: self._lbl_prev_trans.setVisible(checked)
        )
        trans_l.addWidget(self._switch_trans)
        l.addWidget(card_trans)

        # 4. 功能开关卡片：罗马音
        card_roma = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
        roma_l = QHBoxLayout(card_roma)
        roma_l.setContentsMargins(18, 14, 18, 14)

        roma_v = QVBoxLayout()
        roma_v.setSpacing(2)
        lbl_roma_t = QLabel("显示罗马音")
        lbl_roma_t.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
        lbl_roma_d = QLabel("若歌曲包含注音则同步显示")
        lbl_roma_d.setStyleSheet("font-size: 11px; color: #6E7781;")
        lbl_roma_d.setWordWrap(True)
        roma_v.addWidget(lbl_roma_t)
        roma_v.addWidget(lbl_roma_d)
        roma_l.addLayout(roma_v, 1)

        self._switch_roma = MD3Switch()
        self._switch_roma.setChecked(settings.get_show_romaji())
        self._lbl_prev_roma.setVisible(settings.get_show_romaji())
        self._switch_roma.toggled.connect(
            lambda checked: self._lbl_prev_roma.setVisible(checked)
        )
        roma_l.addWidget(self._switch_roma)
        l.addWidget(card_roma)

        # 4. 功能开关卡片：非逐字歌词进度条
        card_prog = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
        prog_l = QHBoxLayout(card_prog)
        prog_l.setContentsMargins(18, 14, 18, 14)

        prog_v = QVBoxLayout()
        prog_v.setSpacing(2)
        lbl_prog_t = QLabel("非逐字歌词进度条")
        lbl_prog_t.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
        lbl_prog_d = QLabel("播放无逐字歌词歌曲时，在当前歌词下方显示单句胶囊进度条")
        lbl_prog_d.setStyleSheet("font-size: 11px; color: #6E7781;")
        lbl_prog_d.setWordWrap(True)
        prog_v.addWidget(lbl_prog_t)
        prog_v.addWidget(lbl_prog_d)
        prog_l.addLayout(prog_v, 1)

        self._switch_progress = MD3Switch()
        self._switch_progress.setChecked(settings.get_show_line_progress())
        prog_l.addWidget(self._switch_progress)
        l.addWidget(card_prog)

        # 5. 功能开关卡片：段落解析
        card_sec = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
        sec_l = QHBoxLayout(card_sec)
        sec_l.setContentsMargins(18, 14, 18, 14)

        sec_v = QVBoxLayout()
        sec_v.setSpacing(2)
        lbl_sec_t = QLabel("歌词段落解析")
        lbl_sec_t.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
        lbl_sec_d = QLabel("识别段落章节与分段角色名，隐藏标记行并将角色同步至翻译行")
        lbl_sec_d.setStyleSheet("font-size: 11px; color: #6E7781;")
        lbl_sec_d.setWordWrap(True)
        sec_v.addWidget(lbl_sec_t)
        sec_v.addWidget(lbl_sec_d)
        sec_l.addLayout(sec_v, 1)

        self._switch_sections = MD3Switch()
        self._switch_sections.setChecked(settings.get_parse_sections())
        sec_l.addWidget(self._switch_sections)
        l.addWidget(card_sec)

        # 4. 全屏歌词上下文数量卡片
        card_fs = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
        fs_l = QVBoxLayout(card_fs)
        fs_l.setContentsMargins(18, 14, 18, 14)
        fs_l.setSpacing(10)

        lbl_fs_t = QLabel("全屏上下文显示行数")
        lbl_fs_t.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
        fs_l.addWidget(lbl_fs_t)

        lbl_fs_d = QLabel("当前高亮歌词上下各显示的行数 (1 ~ 8 行，阶梯渐隐)")
        lbl_fs_d.setStyleSheet("font-size: 11px; color: #6E7781;")
        lbl_fs_d.setWordWrap(True)
        fs_l.addWidget(lbl_fs_d)

        ctrl_fs = QHBoxLayout()
        ctrl_fs.addWidget(QLabel("显示行数：", styleSheet="color: #1B1F24; font-size: 13px;"))
        self._spin_fs_lines = QSpinBox()
        self._spin_fs_lines.setRange(1, 8)
        self._spin_fs_lines.setValue(settings.get_fullscreen_context_lines())
        self._spin_fs_lines.wheelEvent = lambda e: e.ignore()
        ctrl_fs.addWidget(self._spin_fs_lines)
        ctrl_fs.addSpacing(10)
        for num in [3, 4, 5, 6]:
            btn = QPushButton(f"{num}行")
            apply_chip(btn)
            btn.clicked.connect(lambda _, n=num: self._spin_fs_lines.setValue(n))
            ctrl_fs.addWidget(btn)
        ctrl_fs.addStretch()
        fs_l.addLayout(ctrl_fs)

        l.addWidget(card_fs)

        l.addStretch()
        return page

    def _create_lyric_override_card(self) -> QWidget:
        card = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(12)

        # 1. 标题与说明
        top_v = QVBoxLayout()
        top_v.setSpacing(2)
        lbl_title = QLabel("单曲歌词源与版本指定")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
        lbl_desc = QLabel("若歌曲存在多个版本，可以在这里手动指定一个")
        lbl_desc.setStyleSheet("font-size: 11px; color: #6E7781;")
        lbl_desc.setWordWrap(True)
        top_v.addWidget(lbl_title)
        top_v.addWidget(lbl_desc)
        cl.addLayout(top_v)

        # 2. 当前歌曲状态面板
        card_status = MD3Card(bg="#F6F9FE", border="#C6D8F8", radius=12)
        csl = QVBoxLayout(card_status)
        csl.setContentsMargins(12, 10, 12, 10)
        csl.setSpacing(6)

        row_stat = QHBoxLayout()
        row_stat.setSpacing(8)
        lbl_track_desc = QLabel(f"当前识别歌曲：<b>{self._current_title or '（暂无播放）'}</b> {self._current_artist or ''}")
        lbl_track_desc.setStyleSheet("font-size: 12px; color: #1B1F24;")
        lbl_track_desc.setWordWrap(True)
        row_stat.addWidget(lbl_track_desc, 1)

        self._lbl_override_badge = QLabel()
        row_stat.addWidget(self._lbl_override_badge)
        csl.addLayout(row_stat)
        cl.addWidget(card_status)

        # 3. 搜索控制栏
        search_v = QVBoxLayout()
        search_v.setSpacing(8)

        row_search = QHBoxLayout()
        row_search.setSpacing(8)
        self._override_search_edit = QLineEdit()
        self._override_search_edit.setPlaceholderText("输入歌名与歌手进行多版本检索...")
        default_kw = f"{self._current_title} {self._current_artist}".strip()
        self._override_search_edit.setText(default_kw)
        self._override_search_edit.returnPressed.connect(self._do_search_override_versions)
        row_search.addWidget(self._override_search_edit, 1)

        self._btn_do_search = QPushButton("🔍 搜索版本")
        apply_pill_banner_btn(self._btn_do_search)
        self._btn_do_search.clicked.connect(self._do_search_override_versions)
        row_search.addWidget(self._btn_do_search)
        search_v.addLayout(row_search)

        # 平台筛选 Chips
        row_chips = QHBoxLayout()
        row_chips.setSpacing(8)
        row_chips.addWidget(QLabel("检索音源：", styleSheet="font-size: 11px; color: #6E7781;"))

        self._override_provider_filter = "all"
        self._provider_chips = {}
        providers = [("全部音源", "all"), ("网易云音乐", "netease"), ("QQ 音乐", "qqmusic"), ("LRCLIB", "lrclib")]
        for p_name, p_code in providers:
            btn = QPushButton(p_name)
            if p_code == "all":
                apply_chip_active(btn)
            else:
                apply_chip(btn)
            btn.clicked.connect(lambda _, c=p_code: self._set_override_provider(c))
            self._provider_chips[p_code] = btn
            row_chips.addWidget(btn)
        row_chips.addStretch()
        search_v.addLayout(row_chips)
        cl.addLayout(search_v)

        # 4. 搜索结果滚动展示列表
        self._results_scroll = QScrollArea()
        self._results_scroll.setFixedHeight(220)
        self._results_scroll.setWidgetResizable(True)
        self._results_scroll.setStyleSheet("""
            QScrollArea {
                background: #F8FAFD;
                border: 1px solid #DCE3EE;
                border-radius: 12px;
            }
        """)

        self._results_container = QWidget()
        self._results_container.setStyleSheet("background: transparent;")
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(8, 8, 8, 8)
        self._results_layout.setSpacing(6)

        self._lbl_empty_results = QLabel("点击上方“搜索版本”即可拉取各平台候选歌曲列表供您指定选择")
        self._lbl_empty_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_empty_results.setStyleSheet("font-size: 12px; color: #8C939E; padding: 20px 0;")
        self._results_layout.addWidget(self._lbl_empty_results)
        self._results_layout.addStretch()

        self._results_scroll.setWidget(self._results_container)
        cl.addWidget(self._results_scroll)

        # 初始刷新状态 Badge
        self._refresh_override_status_badge()
        return card

    def _set_override_provider(self, p_code: str):
        if self._override_provider_filter == p_code and self._displayed_search_results:
            return
        self._override_provider_filter = p_code
        for code, btn in self._provider_chips.items():
            if code == p_code:
                apply_chip_active(btn)
            else:
                apply_chip(btn)

        kw = self._override_search_edit.text().strip()
        # 如果已经执行了所有音源搜索且搜索词一致，直接在本地内存秒级筛选
        if self._all_search_results and kw == self._all_search_kw:
            if p_code == "all":
                filtered = list(self._all_search_results)
            else:
                filtered = [it for it in self._all_search_results if it.provider.lower() == p_code.lower()]
            self._displayed_search_results = filtered
            self._render_search_results(filtered)

    def _get_current_lyric_info(self) -> tuple[str, str, str]:
        """获取当前生效歌词的提供源代码、提供源显示名与类型 ('netease', '网易云', '标准')"""
        parsed = None
        prov = ""

        # 1. 强优先：若刚刚手动指定了版本，直接使用所选 item 与解析结果
        if getattr(self, "_active_applied_item", None):
            prov = self._active_applied_item.provider
            parsed = getattr(self, "_active_applied_parsed", None)

        # 2. 从本地 SQLite 缓存中获取最新持久化歌词
        if not parsed and self._current_title:
            cached = db_cache.get_song_cache(self._current_title, self._current_artist)
            if cached:
                parsed = cached.get("parsed")
                if not prov:
                    prov = cached.get("provider") or (parsed.provider if parsed else "")

        # 3. 兜底从 controller 内存中获取当前实时 lyrics
        if not parsed and self._controller and hasattr(self._controller, "_lyrics") and self._controller._lyrics:
            ctrl_l = self._controller._lyrics
            parsed = ctrl_l
            if not prov:
                prov = ctrl_l.provider

        prov_clean = (prov or "").lower().strip()
        prov_map = {
            "netease": "网易云",
            "qqmusic": "QQ音乐",
            "lrclib": "LRCLIB",
        }
        prov_name = prov_map.get(prov_clean, prov or "未知源")

        if parsed:
            if parsed.is_instrumental:
                lyric_type = "纯音乐"
            elif parsed.has_words or any(bool(l.words) for l in parsed.lines):
                lyric_type = "动态"
            elif parsed.lines:
                lyric_type = "标准"
            else:
                lyric_type = "无歌词"
        else:
            lyric_type = "标准" if prov else "未获取"

        return prov_clean, prov_name, lyric_type

    def _refresh_override_status_badge(self):
        if not self._current_title:
            self._lbl_override_badge.setText("无正在播放歌曲")
            self._lbl_override_badge.setStyleSheet("background: #F1F3F4; color: #5F6368; border-radius: 6px; padding: 2px 8px; font-size: 11px;")
            return

        prov_code, prov_name, lyric_type = self._get_current_lyric_info()
        self._lbl_override_badge.setText(f"{prov_name} - {lyric_type}")

        if prov_code == "netease":
            self._lbl_override_badge.setStyleSheet("background: #FCE8E6; color: #C5221F; border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: bold;")
        elif prov_code == "qqmusic":
            self._lbl_override_badge.setStyleSheet("background: #E6F4EA; color: #137333; border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: bold;")
        elif prov_code == "lrclib":
            self._lbl_override_badge.setStyleSheet("background: #EEF2F6; color: #3E4C59; border: 1px solid #CFD8DC; border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: bold;")
        else:
            self._lbl_override_badge.setStyleSheet("background: #F1F3F4; color: #5F6368; border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: bold;")

    def _do_search_override_versions(self):
        kw = self._override_search_edit.text().strip()
        if not kw:
            return

        self._btn_do_search.setText("检索中...")
        self._btn_do_search.setEnabled(False)

        # 清空现有结果并显示加载提示
        while self._results_layout.count() > 0:
            it = self._results_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        lbl_loading = QLabel("正在从各平台检索候选版本列表，请稍候...")
        lbl_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_loading.setStyleSheet("font-size: 12px; color: #0B57D0; padding: 20px 0;")
        self._results_layout.addWidget(lbl_loading)
        self._results_layout.addStretch()

        self._search_worker = SearchVersionWorker(kw, self._override_provider_filter, self)

        def on_results(items):
            self._btn_do_search.setText("🔍 搜索版本")
            self._btn_do_search.setEnabled(True)
            self._last_search_results = items
            if self._override_provider_filter == "all":
                self._all_search_results = list(items)
                self._all_search_kw = kw
                self._displayed_search_results = list(items)
            else:
                self._displayed_search_results = list(items)
            self._render_search_results(self._displayed_search_results)

        def on_err(err_msg):
            self._btn_do_search.setText("🔍 搜索版本")
            self._btn_do_search.setEnabled(True)
            while self._results_layout.count() > 0:
                it = self._results_layout.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()
            lbl_err = QLabel(f"检索失败: {err_msg}")
            lbl_err.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_err.setStyleSheet("font-size: 12px; color: #B3261E; padding: 20px 0;")
            self._results_layout.addWidget(lbl_err)
            self._results_layout.addStretch()

        self._search_worker.results_ready.connect(on_results)
        self._search_worker.error_occurred.connect(on_err)
        self._search_worker.start()

    def _render_search_results(self, items: list[SearchSongItem]):
        while self._results_layout.count() > 0:
            it = self._results_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        if not items:
            if self._override_provider_filter != "all" and self._all_search_results:
                lbl = QLabel("当前筛选分类下无匹配的歌曲版本，可点击“全部音源”查看")
            else:
                lbl = QLabel("未找到匹配的歌曲版本，请尝试更改搜索词或音源平台")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 12px; color: #8C939E; padding: 20px 0;")
            self._results_layout.addWidget(lbl)
            self._results_layout.addStretch()
            return

        cached = db_cache.get_song_cache(self._current_title, self._current_artist) if self._current_title else None
        active_song_id = str(cached.get("song_id", "")) if cached else ""
        active_prov = str(cached.get("provider", "")).lower() if cached else ""
        if not active_song_id and self._controller and hasattr(self._controller, "_lyrics") and self._controller._lyrics:
            active_song_id = str(self._controller._lyrics.song_id or "")
            active_prov = str(self._controller._lyrics.provider or "").lower()

        for item in items:
            item_card = QFrame()
            is_match_applied = bool(
                self._active_applied_item and
                self._active_applied_item.provider.lower() == item.provider.lower() and
                (
                    str(item.song_id) == str(self._active_applied_item.song_id) or
                    (item.song_mid and item.song_mid == getattr(self._active_applied_item, "song_mid", "")) or
                    (item.title == self._active_applied_item.title and item.artist == self._active_applied_item.artist)
                )
            )
            is_current = is_match_applied or bool(
                active_prov and item.provider.lower() == active_prov and
                (
                    (active_song_id and str(item.song_id) == active_song_id) or
                    (active_song_id and getattr(item, "song_mid", "") and str(item.song_mid) == active_song_id)
                )
            )
            border_color = "#0B57D0" if is_current else "#E1E8F5"
            bg_color = "#EFF6FF" if is_current else "#FFFFFF"
            item_card.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 10px;
                }}
            """)
            row = QHBoxLayout(item_card)
            row.setContentsMargins(10, 8, 10, 8)
            row.setSpacing(10)

            # 音源徽标
            prov_badge = QLabel()
            if item.provider == "netease":
                prov_badge.setText("网易云")
                prov_badge.setStyleSheet("background: #FCE8E6; color: #C5221F; border-radius: 6px; padding: 2px 6px; font-size: 11px; font-weight: bold;")
            elif item.provider == "qqmusic":
                prov_badge.setText("QQ音乐")
                prov_badge.setStyleSheet("background: #E6F4EA; color: #137333; border-radius: 6px; padding: 2px 6px; font-size: 11px; font-weight: bold;")
            else:
                prov_badge.setText("LRCLIB")
                prov_badge.setStyleSheet("background: #F1F3F4; color: #5F6368; border-radius: 6px; padding: 2px 6px; font-size: 11px; font-weight: bold;")
            row.addWidget(prov_badge)

            # 歌名与歌手信息
            v_info = QVBoxLayout()
            v_info.setSpacing(2)
            title_text = item.title
            if item.sub_name:
                title_text += f" ({item.sub_name})"
            lbl_title = QLabel(title_text)
            lbl_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #1B1F24;")
            lbl_title.setWordWrap(True)

            artist_album = item.artist
            if item.album:
                artist_album += f" · 《{item.album}》"
            lbl_meta = QLabel(artist_album)
            lbl_meta.setStyleSheet("font-size: 11px; color: #6E7781;")
            lbl_meta.setWordWrap(True)

            v_info.addWidget(lbl_title)
            v_info.addWidget(lbl_meta)
            row.addLayout(v_info, 1)

            # 操作按钮
            if is_current:
                btn_used = QPushButton("当前已选 ✓")
                btn_used.setEnabled(False)
                btn_used.setFixedHeight(28)
                btn_used.setStyleSheet("background: #E8F0FE; color: #1967D2; border-radius: 14px; padding: 2px 10px; font-size: 11px; font-weight: bold;")
                row.addWidget(btn_used)
            else:
                btn_apply = QPushButton("选用此版本")
                apply_chip(btn_apply)
                btn_apply.clicked.connect(lambda _, it=item, b=btn_apply: self._on_apply_song_item_clicked(it, b))
                row.addWidget(btn_apply)

            self._results_layout.addWidget(item_card)

        self._results_layout.addStretch()

    def _on_apply_song_item_clicked(self, item: SearchSongItem, btn: QPushButton):
        btn.setText("应用中...")
        btn.setEnabled(False)

        track_title = self._current_title or item.title
        track_artist = self._current_artist or item.artist

        self._apply_worker = ApplyVersionWorker(track_title, track_artist, item, self)

        def on_done(ok, msg, parsed_obj):
            if ok:
                self._active_applied_item = item
                self._active_applied_parsed = parsed_obj
                # 1. 立即通知 controller 重新解析并推送到桌面悬浮窗和全屏
                if self._controller and hasattr(self._controller, "_reload_current_song_lyrics"):
                    self._controller._reload_current_song_lyrics()
                # 2. 刷新设置面板顶部徽标
                self._refresh_override_status_badge()
                # 3. 刷新列表项按钮
                if self._displayed_search_results:
                    self._render_search_results(self._displayed_search_results)
                elif self._last_search_results:
                    self._render_search_results(self._last_search_results)
            else:
                btn.setText("选用此版本")
                btn.setEnabled(True)
                from PyQt6.QtWidgets import QMessageBox
                tip = ""
                if item.provider.lower() == "qqmusic":
                    tip = "\n\n该条目暂未拥有歌词数据，尝试一下其他音源吧。"
                elif item.provider.lower() == "netease":
                    tip = "\n\n该条目暂未拥有歌词数据，尝试一下其他音源吧。"
                QMessageBox.warning(self, "应用失败", f"无法获取此版本的歌词：{msg}{tip}")

        self._apply_worker.apply_finished.connect(on_done)
        self._apply_worker.start()

    def _on_opacity_slider_changed(self, v: int):
        self._lbl_op_val.setText(f"{v}%")
        if self._overlay_widget is not None:
            self._overlay_widget.set_live_opacity(v / 100.0)

    def _set_font_mode(self, mode: str):
        self._font_mode = mode
        font_css = font_manager.get_font_css_family(self._font_items)
        if mode == "fullscreen":
            if hasattr(self, "_panel_ov"):
                self._panel_ov.setVisible(False)
            if hasattr(self, "_panel_fs"):
                self._panel_fs.setVisible(True)
            if hasattr(self, "_btn_mode_fs"):
                self._btn_mode_fs.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #0B57D0;
                        color: #FFFFFF;
                        border-radius: 13px;
                        padding: 0 12px;
                        font-family: {font_css};
                        font-size: 12px;
                        font-weight: 600;
                        border: none;
                    }}
                """)
            if hasattr(self, "_btn_mode_ov"):
                self._btn_mode_ov.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: #475467;
                        border-radius: 13px;
                        padding: 0 12px;
                        font-family: {font_css};
                        font-size: 12px;
                        font-weight: 500;
                        border: none;
                    }}
                    QPushButton:hover {{
                        background-color: #DFE7F5;
                    }}
                """)
        else:
            if hasattr(self, "_panel_ov"):
                self._panel_ov.setVisible(True)
            if hasattr(self, "_panel_fs"):
                self._panel_fs.setVisible(False)
            if hasattr(self, "_btn_mode_ov"):
                self._btn_mode_ov.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #0B57D0;
                        color: #FFFFFF;
                        border-radius: 13px;
                        padding: 0 12px;
                        font-family: {font_css};
                        font-size: 12px;
                        font-weight: 600;
                        border: none;
                    }}
                """)
            if hasattr(self, "_btn_mode_fs"):
                self._btn_mode_fs.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: #475467;
                        border-radius: 13px;
                        padding: 0 12px;
                        font-family: {font_css};
                        font-size: 12px;
                        font-weight: 500;
                        border: none;
                    }}
                    QPushButton:hover {{
                        background-color: #DFE7F5;
                    }}
                """)
        self._update_ui_preview()

    def _update_ui_preview(self):
        active_families = [it.family for it in self._font_items if it.enabled and it.is_valid]
        mode = getattr(self, "_font_mode", "overlay")
        if mode == "fullscreen":
            cur_sz = self._spin_fs_cur.value() if hasattr(self, "_spin_fs_cur") else settings.get_fullscreen_font_size_current()
            sub_sz = max(12, int(cur_sz * 0.6))
            self._lbl_prev_cur.setFont(font_manager.make_app_font(cur_sz, bold=True, families=active_families))
            self._lbl_prev_roma.setFont(font_manager.make_app_font(sub_sz, bold=False, families=active_families))
            self._lbl_prev_trans.setFont(font_manager.make_app_font(sub_sz, bold=False, families=active_families))
        else:
            cur_sz = self._spin_cur.value() if hasattr(self, "_spin_cur") else settings.get_font_size_current()
            ctx_sz = self._spin_ctx.value() if hasattr(self, "_spin_ctx") else settings.get_font_size_context()
            self._lbl_prev_cur.setFont(font_manager.make_app_font(cur_sz, bold=True, families=active_families))
            self._lbl_prev_roma.setFont(font_manager.make_app_font(ctx_sz, bold=False, families=active_families))
            self._lbl_prev_trans.setFont(font_manager.make_app_font(ctx_sz, bold=False, families=active_families))

    # ── TAB 3: 播放器与同步设置 ───────────────────────────────────────────────
    def _create_smtc_page(self) -> QWidget:
        page = QWidget()
        l = QVBoxLayout(page)
        l.setContentsMargins(0, 4, 0, 0)
        l.setSpacing(12)

        # 1. 监听应用白名单
        card_smtc = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
        sl = QVBoxLayout(card_smtc)
        sl.setContentsMargins(18, 14, 18, 14)
        sl.setSpacing(10)

        sl.addWidget(QLabel("监听应用", styleSheet="font-size: 14px; font-weight: 600; color: #1B1F24;"))
        sl.addWidget(
            QLabel("指定监听的音乐进程（留空监听全部）：",
                   styleSheet="font-size: 11px; color: #6E7781;")
        )

        self._apps_edit = QLineEdit()
        self._apps_edit.setPlaceholderText("例如: cloudmusic.exe, Spotify.exe（留空=监听全部）")
        self._apps_edit.setText(", ".join(settings.get_watched_apps()))
        sl.addWidget(self._apps_edit)

        # 快捷添加应用药丸
        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(8)
        preset_layout.addWidget(QLabel("快捷添加：", styleSheet="font-size: 11px; color: #6E7781;"))
        presets = [
            ("网易云", "cloudmusic.exe"),
            ("Spotify", "Spotify.exe"),
            ("QQ 音乐", "QQMusic.exe"),
        ]
        for name, exe in presets:
            btn = QPushButton(f"+ {name}")
            apply_chip(btn)
            btn.clicked.connect(lambda _, e=exe: self._add_app_preset(e))
            preset_layout.addWidget(btn)

        btn_clear = QPushButton("全部监听")
        apply_chip(btn_clear)
        btn_clear.clicked.connect(lambda: self._apps_edit.setText(""))
        preset_layout.addWidget(btn_clear)
        preset_layout.addStretch()
        sl.addLayout(preset_layout)

        l.addWidget(card_smtc)

        # 2. 歌词时间偏移同步微调
        card_sync = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
        syncl = QVBoxLayout(card_sync)
        syncl.setContentsMargins(18, 14, 18, 14)
        syncl.setSpacing(12)

        syncl.addWidget(QLabel("歌词同步与时间微调", styleSheet="font-size: 14px; font-weight: 600; color: #1B1F24;"))
        syncl.addWidget(
            QLabel("单位：毫秒（正值提前，负值延后）",
                   styleSheet="font-size: 11px; color: #6E7781;")
        )

        # ── 子区块 1：当前正在播放歌曲单独微调 ──────────────────────────────────
        card_cur_song = MD3Card(bg="#F6F9FE", border="#C6D8F8", radius=14)
        csl = QVBoxLayout(card_cur_song)
        csl.setContentsMargins(14, 12, 14, 12)
        csl.setSpacing(8)

        if self._current_title:
            row_song_header = QHBoxLayout()
            row_song_header.setSpacing(12)

            # 封面缩略图
            self._cover_widget = CoverThumbnailWidget(thumb_bytes=self._thumb_bytes, size=52)
            row_song_header.addWidget(self._cover_widget)

            # 右侧：当前歌曲名称与单曲专属配置复选框
            v_song_meta = QVBoxLayout()
            v_song_meta.setSpacing(6)

            song_display = settings.make_song_key(self._current_title, self._current_artist)
            lbl_song_name = QLabel(f"当前歌曲：{song_display}")
            lbl_song_name.setStyleSheet("font-size: 13px; font-weight: 700; color: #0B57D0;")
            lbl_song_name.setWordWrap(True)
            v_song_meta.addWidget(lbl_song_name)

            row_chk_badge = QHBoxLayout()
            self._chk_song_custom = QCheckBox("为此歌曲单独设置偏移")
            self._chk_song_custom.setStyleSheet("font-size: 12px; font-weight: 600; color: #1B1F24;")
            row_chk_badge.addWidget(self._chk_song_custom)
            row_chk_badge.addSpacing(10)

            self._lbl_live_offset_badge = QLabel("实时生效：0ms")
            self._lbl_live_offset_badge.setStyleSheet(
                "background: #E8F0FE; color: #1967D2; border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: bold;"
            )
            row_chk_badge.addWidget(self._lbl_live_offset_badge)
            row_chk_badge.addStretch()
            v_song_meta.addLayout(row_chk_badge)

            row_song_header.addLayout(v_song_meta, 1)
            csl.addLayout(row_song_header)

            # 微调 SpinBox 与快捷药丸
            row_song_spin = QHBoxLayout()
            self._spin_song_off = QSpinBox()
            self._spin_song_off.setRange(-30000, 30000)
            self._spin_song_off.setSingleStep(100)

            # 获取当前歌是否已有单独配置
            existing_song_off = db_cache.get_song_offset(self._current_title, self._current_artist)
            if existing_song_off is not None:
                self._chk_song_custom.setChecked(True)
                self._spin_song_off.setValue(existing_song_off)
                self._spin_song_off.setEnabled(True)
            else:
                self._chk_song_custom.setChecked(False)
                self._spin_song_off.setValue(settings.get_offset_ms())
                self._spin_song_off.setEnabled(False)

            row_song_spin.addWidget(self._spin_song_off)
            row_song_spin.addSpacing(6)

            def _adjust_song_offset(delta: int):
                if delta == 0:
                    self._spin_song_off.setValue(0)
                else:
                    self._spin_song_off.setValue(self._spin_song_off.value() + delta)

            self._song_chip_buttons = []
            for off, txt in [(-500, "-0.5s"), (-100, "-0.1s"), (0, "0s"), (100, "+0.1s"), (500, "+0.5s")]:
                btn = QPushButton(txt)
                apply_chip(btn)
                btn.clicked.connect(lambda _, o=off: _adjust_song_offset(o))
                row_song_spin.addWidget(btn)
                self._song_chip_buttons.append(btn)

            row_song_spin.addStretch()
            csl.addLayout(row_song_spin)

            def _toggle_song_custom(checked: bool):
                self._spin_song_off.setEnabled(checked)
                for b in self._song_chip_buttons:
                    b.setEnabled(checked)
                if not checked and hasattr(self, "_spin_off"):
                    self._spin_song_off.setValue(self._spin_off.value())
                self._update_live_offset_preview()

            self._chk_song_custom.toggled.connect(_toggle_song_custom)
            self._spin_song_off.valueChanged.connect(lambda _: self._update_live_offset_preview())
            _toggle_song_custom(self._chk_song_custom.isChecked())
        else:
            self._chk_song_custom = None
            self._spin_song_off = None
            self._lbl_live_offset_badge = None
            self._song_chip_buttons = []
            lbl_no_song = QLabel("当前未检测到播放中的歌曲。播放时可在此单独微调。")
            lbl_no_song.setStyleSheet("font-size: 12px; color: #6E7781; line-height: 1.4;")
            csl.addWidget(lbl_no_song)

        syncl.addWidget(card_cur_song)

        # ── 子区块 2：全局默认歌词延迟微调 ────────────────────────────────────
        syncl.addWidget(QLabel("全局默认偏移：", styleSheet="font-size: 13px; font-weight: 600; color: #1B1F24;"))
        row_global_spin = QHBoxLayout()
        self._spin_off = QSpinBox()
        self._spin_off.setRange(-30000, 30000)
        self._spin_off.setSingleStep(100)
        self._spin_off.setValue(settings.get_offset_ms())
        self._spin_off.valueChanged.connect(lambda _: self._update_live_offset_preview())
        row_global_spin.addWidget(self._spin_off)
        row_global_spin.addSpacing(6)

        def _adjust_global_offset(delta: int):
            if delta == 0:
                self._spin_off.setValue(0)
            else:
                self._spin_off.setValue(self._spin_off.value() + delta)

        for off, txt in [(-500, "-0.5s"), (-100, "-0.1s"), (0, "0s"), (100, "+0.1s"), (500, "+0.5s")]:
            btn = QPushButton(txt)
            apply_chip(btn)
            btn.clicked.connect(lambda _, o=off: _adjust_global_offset(o))
            row_global_spin.addWidget(btn)

        row_global_spin.addStretch()
        syncl.addLayout(row_global_spin)

        # ── 子区块 3：已单独配置的歌曲列表与管理 ──────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #E1E8F5; margin-top: 4px; margin-bottom: 4px;")
        syncl.addWidget(sep)

        row_list_header = QHBoxLayout()
        self._lbl_custom_songs_count = QLabel("已单独配置的歌曲列表", styleSheet="font-size: 13px; font-weight: 600; color: #1B1F24;")
        row_list_header.addWidget(self._lbl_custom_songs_count)
        row_list_header.addStretch()
        syncl.addLayout(row_list_header)

        self._custom_songs_container = QVBoxLayout()
        self._custom_songs_container.setSpacing(6)
        syncl.addLayout(self._custom_songs_container)
        self._render_custom_songs_list()

        # 初始同步一次实时微调提示
        self._update_live_offset_preview()

        l.addWidget(card_sync)
        l.addStretch()
        return page

    def _update_live_offset_preview(self):
        """实时更新当前生效的偏移量预览到播放时间轴"""
        if not hasattr(self, "_spin_off"):
            return
        if self._current_title and hasattr(self, "_chk_song_custom") and self._chk_song_custom is not None:
            if self._chk_song_custom.isChecked() and hasattr(self, "_spin_song_off") and self._spin_song_off is not None:
                live_val = self._spin_song_off.value()
            else:
                live_val = self._spin_off.value()
        else:
            live_val = self._spin_off.value()

        if hasattr(self, "_lbl_live_offset_badge") and self._lbl_live_offset_badge is not None:
            sign_str = f"+{live_val}ms" if live_val > 0 else f"{live_val}ms"
            self._lbl_live_offset_badge.setText(f"实时生效：{sign_str}")

        if hasattr(self, "_controller") and self._controller:
            self._controller.preview_offset(live_val)

    def _render_custom_songs_list(self):
        while self._custom_songs_container.count():
            item = self._custom_songs_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        count = len(self._song_offsets_draft)
        self._lbl_custom_songs_count.setText(f"已单独配置的歌曲 ({count} 首)")

        if not self._song_offsets_draft:
            empty_lbl = QLabel("暂无单独配置的歌曲记录。")
            empty_lbl.setStyleSheet("color: #8C939E; font-size: 12px; padding: 4px 2px;")
            self._custom_songs_container.addWidget(empty_lbl)
            return

        for song_key, offset_val in list(self._song_offsets_draft.items()):
            row_widget = QFrame()
            row_widget.setStyleSheet("""
                QFrame {
                    background: #F8FAFD;
                    border: 1px solid #E1E8F5;
                    border-radius: 10px;
                    padding: 4px 10px;
                }
            """)
            rl = QHBoxLayout(row_widget)
            rl.setContentsMargins(6, 4, 6, 4)
            rl.setSpacing(10)

            lbl_name = QLabel(song_key)
            lbl_name.setStyleSheet("font-size: 12px; font-weight: 600; color: #1B1F24;")
            rl.addWidget(lbl_name, 1)

            # 偏移微调 SpinBox
            spin = QSpinBox()
            spin.setRange(-30000, 30000)
            spin.setSingleStep(100)
            spin.setValue(offset_val)
            spin.setFixedWidth(90)
            spin.valueChanged.connect(lambda val, k=song_key: self._on_draft_song_offset_changed(k, val))
            rl.addWidget(spin)

            sign_str = f"+{offset_val}ms" if offset_val > 0 else f"{offset_val}ms"
            badge = QLabel(sign_str)
            badge.setStyleSheet("background: #E8F0FE; color: #1967D2; border-radius: 6px; padding: 2px 6px; font-size: 11px; font-weight: bold;")
            badge.setFixedWidth(65)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rl.addWidget(badge)
            spin.valueChanged.connect(lambda val, b=badge: b.setText(f"+{val}ms" if val > 0 else f"{val}ms"))

            # 删除按钮
            btn_del = QPushButton("✕")
            apply_circle_btn(btn_del, 24)
            btn_del.setToolTip("移除此歌曲的单独配置（恢复使用全局默认偏移）")
            btn_del.clicked.connect(lambda _, k=song_key: self._remove_draft_song_offset(k))
            rl.addWidget(btn_del)

            self._custom_songs_container.addWidget(row_widget)

    def _on_draft_song_offset_changed(self, song_key: str, val: int):
        self._song_offsets_draft[song_key] = val
        # 如果修改的是当前正在播放的歌曲，同步到当前歌曲 spinbox 并实时预览
        if self._current_title and hasattr(self, "_spin_song_off") and self._spin_song_off is not None:
            cur_key = settings.make_song_key(self._current_title, self._current_artist)
            if song_key == cur_key:
                self._spin_song_off.blockSignals(True)
                self._spin_song_off.setValue(val)
                self._spin_song_off.blockSignals(False)
                self._update_live_offset_preview()

    def _remove_draft_song_offset(self, song_key: str):
        self._song_offsets_draft.pop(song_key, None)
        # 如果删除的是当前播放的歌曲，同步取消专属勾选
        if self._current_title and hasattr(self, "_chk_song_custom") and self._chk_song_custom is not None:
            cur_key = settings.make_song_key(self._current_title, self._current_artist)
            if song_key == cur_key:
                self._chk_song_custom.setChecked(False)
        self._render_custom_songs_list()
        self._update_live_offset_preview()

    def _add_app_preset(self, app_name: str):
        cur = [a.strip() for a in self._apps_edit.text().split(",") if a.strip()]
        if app_name not in cur:
            cur.append(app_name)
            self._apps_edit.setText(", ".join(cur))

    # ── 恢复默认 ─────────────────────────────────────────────────────────────
    def _reset_defaults(self):
        # 恢复默认设置
        self._slider_op.setValue(85)
        self._spin_cur.setValue(28)
        self._spin_ctx.setValue(14)
        if hasattr(self, "_spin_fs_cur"):
            self._spin_fs_cur.setValue(38)
        if hasattr(self, "_spin_fs_ctx"):
            self._spin_fs_ctx.setValue(18)
        self._switch_trans.setChecked(True)
        self._switch_roma.setChecked(False)
        self._switch_progress.setChecked(True)
        self._switch_sections.setChecked(True)
        self._spin_fs_lines.setValue(5)
        self._apps_edit.setText("cloudmusic.exe")
        self._spin_off.setValue(0)
        if self._current_title and hasattr(self, "_chk_song_custom") and self._chk_song_custom is not None:
            self._chk_song_custom.setChecked(False)
            self._spin_song_off.setValue(0)
            self._spin_song_off.setEnabled(False)
        self._song_offsets_draft.clear()
        self._render_custom_songs_list()
        self._update_live_offset_preview()
        for item in self._font_items:
            item.enabled = True
        self._render_font_items()
        self._refresh_dialog_fonts()

    # ── 保存并应用 ───────────────────────────────────────────────────────────
    def _save_and_apply(self):
        # 1. 字体配置持久化
        font_manager.save_font_items(self._font_items)

        # 2. 其它常规设置持久化
        apps_raw = self._apps_edit.text()
        apps = [a.strip() for a in apps_raw.split(",") if a.strip()]
        settings.set_watched_apps(apps)
        settings.set_show_translation(self._switch_trans.isChecked())
        settings.set_show_romaji(self._switch_roma.isChecked())
        settings.set_show_line_progress(self._switch_progress.isChecked())
        settings.set_parse_sections(self._switch_sections.isChecked())
        settings.set_font_size_current(self._spin_cur.value())
        settings.set_font_size_context(self._spin_ctx.value())
        if hasattr(self, "_spin_fs_cur"):
            settings.set_fullscreen_font_size_current(self._spin_fs_cur.value())
        if hasattr(self, "_spin_fs_ctx"):
            settings.set_fullscreen_font_size_context(self._spin_fs_ctx.value())
        settings.set_opacity(self._slider_op.value() / 100.0)
        settings.set_offset_ms(self._spin_off.value())
        settings.set_fullscreen_context_lines(self._spin_fs_lines.value())

        # 3. 歌曲独立偏移配置持久化到数据库
        if self._current_title and hasattr(self, "_chk_song_custom") and self._chk_song_custom is not None:
            cur_key = settings.make_song_key(self._current_title, self._current_artist)
            if self._chk_song_custom.isChecked():
                val = self._spin_song_off.value()
                self._song_offsets_draft[cur_key] = val
                db_cache.set_song_offset(self._current_title, self._current_artist, val)
            else:
                self._song_offsets_draft.pop(cur_key, None)
                self._song_offsets_draft.pop(f"{self._current_title}|||{self._current_artist}", None)
                db_cache.remove_song_offset(self._current_title, self._current_artist)

        db_cache.set_all_song_offsets(self._song_offsets_draft)

        self.accept()
