"""
gui/settings_dialog.py — 设置面板
"""
from __future__ import annotations

from .settings import SettingsDialog
from .settings.styles import (
    apply_circle_btn,
    apply_chip,
    apply_chip_active,
    apply_pill_banner_btn,
    apply_pill_outlined,
    apply_pill_primary,
    apply_pill_tonal,
    build_dialog_stylesheet,
)
from .settings.widgets import (
    ColorSwatchButton,
    CoverThumbnailWidget,
    LyricPreviewProgressBar,
    MD3Card,
    MD3Switch,
)
from .settings.workers import ApplyVersionWorker, SearchVersionWorker

__all__ = [
    "SettingsDialog",
    "MD3Switch",
    "MD3Card",
    "CoverThumbnailWidget",
    "ColorSwatchButton",
    "LyricPreviewProgressBar",
    "SearchVersionWorker",
    "ApplyVersionWorker",
    "build_dialog_stylesheet",
    "apply_pill_primary",
    "apply_pill_tonal",
    "apply_pill_outlined",
    "apply_circle_btn",
    "apply_chip",
    "apply_pill_banner_btn",
    "apply_chip_active",
]
