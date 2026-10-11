"""
gui/settings/styles.py — MD3 样式表与按钮样式辅助工具
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton

from core import font_manager


def build_dialog_stylesheet(font_css: str = "", primary_hex: str = "#0B57D0", container_hex: str = "#D3E3FD") -> str:
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
    background-color: {primary_hex};
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
    opacity: 0.9;
}}

QLabel, QPushButton, QLineEdit, QSpinBox, QComboBox {{
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
    background: {primary_hex};
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
    selection-background-color: {container_hex};
    selection-color: #041E49;
}}
QLineEdit:focus {{
    border: 2px solid {primary_hex};
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
    border: 2px solid {primary_hex};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 20px;
    border: none;
    background: transparent;
}}

/* 下拉选择框 */
QComboBox {{
    background: #FFFFFF;
    border: 1.5px solid #DCE3EE;
    border-radius: 14px;
    color: #1B1F24;
    font-family: {font_css};
    padding: 6px 14px;
    font-size: 13px;
    min-width: 150px;
}}
QComboBox:focus, QComboBox:hover {{
    border: 1.5px solid {primary_hex};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: #FFFFFF;
    border: 1.5px solid #DCE3EE;
    border-radius: 12px;
    color: #1B1F24;
    font-family: {font_css};
    selection-background-color: {container_hex};
    selection-color: #041E49;
    padding: 4px;
    outline: none;
}}

/* 滑动条 */
QSlider::groove:horizontal {{
    height: 6px;
    background: #E1E8F5;
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {primary_hex};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    width: 20px;
    height: 20px;
    margin: -7px 0;
    background: {primary_hex};
    border: 2.5px solid #FFFFFF;
    border-radius: 10px;
}}
QSlider::handle:horizontal:hover {{
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


def apply_pill_primary(btn: QPushButton, font_css: str = "", primary_hex: str = "#0B57D0") -> None:
    if not font_css:
        font_css = font_manager.get_font_css_family()
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {primary_hex};
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
            background-color: {primary_hex};
            opacity: 0.9;
        }}
        QPushButton:pressed {{
            background-color: {primary_hex};
            opacity: 0.8;
        }}
    """)


def apply_pill_tonal(btn: QPushButton, font_css: str = "") -> None:
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


def apply_pill_outlined(btn: QPushButton, font_css: str = "") -> None:
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


def apply_circle_btn(btn: QPushButton, size: int = 32, font_css: str = "") -> None:
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


def apply_chip(btn: QPushButton, font_css: str = "") -> None:
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


def apply_pill_banner_btn(btn: QPushButton, font_css: str = "") -> None:
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


def apply_chip_active(btn: QPushButton, font_css: str = "") -> None:
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
