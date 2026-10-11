"""
gui/settings/font_page.py — 字体管理与渲染设置页面
"""
from __future__ import annotations

import copy

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core import font_manager
from core.font_manager import FontItem

from .styles import apply_circle_btn, apply_pill_banner_btn
from .widgets import MD3Card, MD3Switch


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
    info_desc = QLabel("将会按顺序优先使用字体")
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
    while self._font_list_layout.count():
        item = self._font_list_layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()

    if not self._font_items:
        empty_lbl = QLabel("data/fonts/ 目录下暂未扫描到字体文件\n可放置在目录后重新扫描")
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

    row1 = QHBoxLayout()
    row1.setSpacing(10)

    # 圆形序号徽标
    badge = QLabel(f"#{index + 1}" if item.enabled else "关")
    badge.setFixedSize(38, 26)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    primary_hex = getattr(self, "_current_primary_hex", "#0B57D0")
    container_hex = getattr(self, "_current_container_hex", "#D3E3FD")
    if item.enabled:
        badge.setStyleSheet(
            f"background: {container_hex}; color: {primary_hex}; border-radius: 13px; font-weight: bold; font-size: 12px;"
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
    scanned = font_manager.scan_fonts()
    self._font_items = copy.deepcopy(scanned)
    self._render_font_items()
    self._refresh_dialog_fonts()
