"""
gui/settings/__init__.py — 设置面板模块入口与主对话框
"""
from __future__ import annotations

import copy
from typing import Optional

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core import color_theme, db_cache, font_manager, settings
from core.font_manager import FontItem
from core.providers.base import SearchSongItem

from .styles import (
    apply_circle_btn,
    apply_pill_banner_btn,
    apply_pill_outlined,
    apply_pill_primary,
    apply_pill_tonal,
    build_dialog_stylesheet,
)
from .widgets import MD3Switch
from .workers import ApplyVersionWorker, SearchVersionWorker


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
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
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

        # 主题色彩方案草稿状态
        self._draft_theme_preset: str = settings.get_theme_preset()
        self._draft_seed_color: str = settings.get_theme_seed_color()
        self._draft_theme_colors: dict[str, str] = dict(settings.get_theme_colors())
        if "custom" in color_theme.PRESET_THEMES and self._draft_theme_preset == "custom":
            color_theme.PRESET_THEMES["custom"]["colors"] = dict(self._draft_theme_colors)
            color_theme.PRESET_THEMES["custom"]["seed_color"] = self._draft_seed_color
        self._color_editor_swatches: dict = {}
        self._color_editor_edits: dict = {}
        self._preset_buttons: dict[str, QPushButton] = {}
        self._preset_dots: dict[str, list[QFrame]] = {}
        self._current_primary_hex: str = "#0B57D0"
        self._current_container_hex: str = "#D3E3FD"

        self._build_ui()

    def reject(self):
        # 取消时还原悬浮窗实时不透明度与初始偏移量
        if self._overlay_widget:
            self._overlay_widget.set_live_opacity(self._initial_opacity)
        if hasattr(self, "_controller") and self._controller:
            self._controller.preview_offset(self._initial_offset)
        super().reject()

    def _center_on_screen(self):
        if self._has_centered:
            return
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            self.move(
                screen_geo.center().x() - self.width() // 2,
                screen_geo.center().y() - self.height() // 2,
            )
        self._has_centered = True

    def showEvent(self, event):
        super().showEvent(event)
        if not self._has_centered:
            self._center_on_screen()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if event.position().y() <= 80:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def _build_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(14, 14, 14, 14)
        outer_layout.setSpacing(0)

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

        root = QVBoxLayout(self._main_card)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(14)

        self._icon_badge = QLabel("♫")
        self._icon_badge.setFixedSize(40, 40)
        self._icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_badge.setStyleSheet(
            "background: #D3E3FD; color: #0B57D0; border-radius: 20px; font-size: 20px; font-weight: bold;"
        )
        header.addWidget(self._icon_badge)

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

        nav_container = QFrame()
        nav_container.setStyleSheet(
            "background: #EDF2FA; border-radius: 22px; padding: 3px;"
        )
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(4, 4, 4, 4)
        nav_layout.setSpacing(6)

        self._btn_tab_font = QPushButton("字体设置")
        self._btn_tab_ui = QPushButton("歌词显示")
        self._btn_tab_theme = QPushButton("配色方案")
        self._btn_tab_smtc = QPushButton("播放与同步")

        self._nav_buttons = [
            self._btn_tab_font,
            self._btn_tab_ui,
            self._btn_tab_theme,
            self._btn_tab_smtc,
        ]
        for i, b in enumerate(self._nav_buttons):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(36)
            b.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
            nav_layout.addWidget(b)

        root.addWidget(nav_container)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._create_font_page())
        self._stack.addWidget(self._make_scrollable(self._create_ui_page()))
        self._stack.addWidget(self._make_scrollable(self._create_theme_page()))
        self._stack.addWidget(self._make_scrollable(self._create_smtc_page()))
        root.addWidget(self._stack, 1)

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

        self._switch_tab(0)

        self._sync_dialog_theme()

    def _switch_tab(self, idx: int):
        self._stack.setCurrentIndex(idx)
        w = self._stack.widget(idx)
        if isinstance(w, QScrollArea):
            w.verticalScrollBar().setValue(0)
        font_css = font_manager.get_font_css_family(self._font_items)
        primary_hex = getattr(self, "_current_primary_hex", "#0B57D0")
        container_hex = getattr(self, "_current_container_hex", "#D3E3FD")
        for i, b in enumerate(self._nav_buttons):
            if i == idx:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {primary_hex};
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
                        background-color: {container_hex};
                        color: {primary_hex};
                    }}
                """)

    def _refresh_dialog_fonts(self):
        font_css = font_manager.get_font_css_family(self._font_items)
        primary_hex = getattr(self, "_current_primary_hex", "#0B57D0")
        container_hex = getattr(self, "_current_container_hex", "#D3E3FD")
        self.setStyleSheet(build_dialog_stylesheet(font_css, primary_hex, container_hex))
        self.setFont(
            font_manager.make_app_font(
                13,
                families=[it.family for it in self._font_items if it.enabled and it.is_valid]
                + font_manager.SYSTEM_FALLBACK_FAMILIES,
            )
        )
        self._switch_tab(self._stack.currentIndex())
        if hasattr(self, "_btn_reset"):
            self._btn_reset.setStyleSheet(f"""
                QPushButton {{
                    background-color: #FFFFFF;
                    color: {primary_hex};
                    border: 1.5px solid {primary_hex};
                    border-radius: 19px;
                    padding: 8px 22px;
                    font-family: {font_css};
                    font-size: 13px;
                    font-weight: 600;
                    outline: none;
                }}
                QPushButton:hover {{
                    background-color: {container_hex};
                    border-color: {primary_hex};
                }}
            """)
        if hasattr(self, "_btn_cancel"):
            apply_pill_tonal(self._btn_cancel, font_css)
        if hasattr(self, "_btn_save"):
            apply_pill_primary(self._btn_save, font_css, primary_hex)
        if hasattr(self, "_btn_folder"):
            apply_pill_banner_btn(self._btn_folder, font_css)
        if hasattr(self, "_btn_rescan"):
            apply_pill_banner_btn(self._btn_rescan, font_css)
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

    # 引入外部页面 mixin 方法
    from .font_page import (
        _create_font_page,
        _create_single_font_card,
        _move_font,
        _on_font_toggled,
        _render_font_items,
        _rescan_fonts,
    )
    from .smtc_page import (
        _add_app_preset,
        _create_smtc_page,
        _on_draft_song_offset_changed,
        _remove_draft_song_offset,
        _render_custom_songs_list,
        _reset_defaults,
        _save_and_apply,
        _update_live_offset_preview,
    )
    from .theme_page import (
        _apply_preset_draft,
        _create_theme_details_card,
        _create_theme_md_generator_card,
        _create_theme_page,
        _create_theme_presets_card,
        _create_theme_preview_card,
        _generate_from_seed,
        _on_color_hex_edited,
        _on_color_swatch_changed,
        _on_seed_color_picked,
        _on_seed_hex_edited,
        _on_seed_hex_finished,
        _refresh_theme_preset_buttons,
        _refresh_theme_ui,
        _sync_dialog_theme,
        _update_theme_preview,
    )
    from .ui_page import (
        _create_lyric_override_card,
        _create_ui_page,
        _do_search_override_versions,
        _get_current_lyric_info,
        _on_apply_song_item_clicked,
        _on_opacity_slider_changed,
        _refresh_override_status_badge,
        _refresh_preview_visibility,
        _render_search_results,
        _set_font_mode,
        _set_override_provider,
        _update_ui_preview,
    )
