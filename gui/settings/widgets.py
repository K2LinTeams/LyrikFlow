"""
gui/settings/widgets.py — 设置面板专用自定义组件
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QAbstractButton, QColorDialog, QFrame, QPushButton, QWidget

from core import color_theme


def lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, float(t)))
    r = int(c1.red() + (c2.red() - c1.red()) * t)
    g = int(c1.green() + (c2.green() - c1.green()) * t)
    b = int(c1.blue() + (c2.blue() - c1.blue()) * t)
    return QColor(r, g, b)


class MD3Switch(QAbstractButton):
    GLOBAL_ACTIVE_COLOR = QColor("#0B57D0")

    @classmethod
    def set_global_active_color(cls, col_hex: str):
        cls.GLOBAL_ACTIVE_COLOR = QColor(col_hex)

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
        active_col = getattr(MD3Switch, "GLOBAL_ACTIVE_COLOR", QColor("#0B57D0"))
        if self.isEnabled():
            track_color = lerp_color(QColor("#E3E8F0"), active_col, t)
            thumb_color = lerp_color(QColor("#5A6A80"), QColor("#FFFFFF"), t)
            border_color = lerp_color(QColor("#C4D0E3"), active_col, t)
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


class MD3Card(QFrame):
    def __init__(self, parent=None, bg="#FFFFFF", border="#E1E8F5", radius=18):
        super().__init__(parent)
        self.setStyleSheet(
            f"MD3Card {{ background: {bg}; border: 1.5px solid {border}; border-radius: {radius}px; }}"
        )


class CoverThumbnailWidget(QWidget):
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


class ColorSwatchButton(QPushButton):
    colorChanged = pyqtSignal(str)

    def __init__(self, color_hex: str = "#FFFFFF", size: int = 32, parent=None):
        super().__init__(parent)
        self._color_hex = color_hex.upper()
        self._size = size
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("点击选择颜色")
        self.clicked.connect(self._on_click)

    def get_color(self) -> str:
        return self._color_hex

    def set_color(self, hex_val: str):
        if color_theme.is_valid_hex(hex_val):
            self._color_hex = color_theme.normalize_hex(hex_val)
            self.update()

    def _on_click(self):
        cur_qcol = QColor(self._color_hex)
        chosen = QColorDialog.getColor(cur_qcol, self.window(), "选择颜色")
        if chosen.isValid():
            hex_str = chosen.name(QColor.NameFormat.HexRgb).upper()
            self.set_color(hex_str)
            self.colorChanged.emit(hex_str)

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = float(self.width()), float(self.height())
        rect = QRectF(2.0, 2.0, w - 4.0, h - 4.0)

        col = QColor(self._color_hex)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(col)
        painter.drawRoundedRect(rect, 9.0, 9.0)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(0, 0, 0, 45), 1.2))
        painter.drawRoundedRect(rect, 9.0, 9.0)

        painter.setPen(QPen(QColor(255, 255, 255, 130), 1.0))
        painter.drawRoundedRect(rect.adjusted(1.0, 1.0, -1.0, -1.0), 8.0, 8.0)


class LyricPreviewProgressBar(QWidget):
    def __init__(self, start_hex: str = "#FFFFFF", end_hex: str = "#A0E6FF", parent=None):
        super().__init__(parent)
        self._start_hex = start_hex
        self._end_hex = end_hex
        self.setFixedHeight(12)

    def set_colors(self, start_hex: str, end_hex: str):
        self._start_hex = start_hex
        self._end_hex = end_hex
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = float(self.width())
        h = float(self.height())
        bar_h = 4.0
        y = (h - bar_h) / 2.0

        track_rect = QRectF(0.0, y, w, bar_h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 45))
        painter.drawRoundedRect(track_rect, 2.0, 2.0)

        fill_w = max(bar_h, w * 0.52)
        fill_rect = QRectF(0.0, y, fill_w, bar_h)
        grad = QLinearGradient(0.0, 0.0, w, 0.0)
        grad.setColorAt(0.0, QColor(self._start_hex))
        grad.setColorAt(1.0, QColor(self._end_hex))
        painter.setBrush(grad)
        painter.drawRoundedRect(fill_rect, 2.0, 2.0)


class KaraokePreviewLabel(QWidget):
    def __init__(self, text: str = "不可解で不完全な魔法", active_hex: str = "#FFFFFF", inactive_hex: str = "#A0A8B8", progress: float = 0.52, parent=None):
        super().__init__(parent)
        self._text = text
        self._active_hex = active_hex
        self._inactive_hex = inactive_hex
        self._progress = max(0.0, min(1.0, float(progress)))
        self.setFixedHeight(34)

    def set_colors(self, active_hex: str, inactive_hex: str):
        self._active_hex = active_hex
        self._inactive_hex = inactive_hex
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        f = QFont(self.font())
        f.setPixelSize(20)
        f.setBold(True)
        painter.setFont(f)

        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(self._text)
        h = float(self.height())
        baseline = (h + fm.ascent() - fm.descent()) / 2.0
        start_x = 0.0

        painter.setPen(QColor(self._inactive_hex))
        painter.drawText(int(start_x), int(baseline), self._text)

        prog_w = text_w * self._progress
        if prog_w > 0:
            painter.save()
            painter.setClipRect(QRectF(start_x, 0, prog_w, h))
            painter.setPen(QColor(self._active_hex))
            painter.drawText(int(start_x), int(baseline), self._text)
            painter.restore()

