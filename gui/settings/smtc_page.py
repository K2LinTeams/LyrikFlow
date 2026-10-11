"""
gui/settings/smtc_page.py — 播放器监听与歌词时间偏移同步微调设置页面
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core import db_cache, font_manager, settings

from .styles import apply_circle_btn, apply_chip
from .widgets import CoverThumbnailWidget, MD3Card


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
        QLabel("指定要监听的进程",
               styleSheet="font-size: 11px; color: #6E7781;")
    )

    self._apps_edit = QLineEdit()
    self._apps_edit.setPlaceholderText("例如: cloudmusic.exe, Spotify.exe（留空=监听全部）")
    self._apps_edit.setText(", ".join(settings.get_watched_apps()))
    sl.addWidget(self._apps_edit)

    preset_layout = QHBoxLayout()
    preset_layout.setSpacing(8)
    preset_layout.addWidget(QLabel("快捷添加", styleSheet="font-size: 11px; color: #6E7781;"))
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

    syncl.addWidget(QLabel("歌词同步微调", styleSheet="font-size: 14px; font-weight: 600; color: #1B1F24;"))
    syncl.addWidget(
        QLabel("正值提前，负值延后 单位为毫秒",
               styleSheet="font-size: 11px; color: #6E7781;")
    )

    card_cur_song = MD3Card(bg="#F6F9FE", border="#C6D8F8", radius=14)
    csl = QVBoxLayout(card_cur_song)
    csl.setContentsMargins(14, 12, 14, 12)
    csl.setSpacing(8)

    if self._current_title:
        row_song_header = QHBoxLayout()
        row_song_header.setSpacing(12)

        self._cover_widget = CoverThumbnailWidget(thumb_bytes=self._thumb_bytes, size=52)
        row_song_header.addWidget(self._cover_widget)

        v_song_meta = QVBoxLayout()
        v_song_meta.setSpacing(6)

        song_display = settings.make_song_key(self._current_title, self._current_artist)
        lbl_song_name = QLabel(f"当前歌曲：{song_display}")
        lbl_song_name.setStyleSheet("font-size: 13px; font-weight: 700; color: #0B57D0;")
        lbl_song_name.setWordWrap(True)
        v_song_meta.addWidget(lbl_song_name)

        row_chk_badge = QHBoxLayout()
        self._chk_song_custom = QCheckBox("为此歌曲单独设置偏移量")
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

        row_song_spin = QHBoxLayout()
        self._spin_song_off = QSpinBox()
        self._spin_song_off.setRange(-30000, 30000)
        self._spin_song_off.setSingleStep(100)

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
        lbl_no_song = QLabel("当前未检测到播放中的歌曲 播放时可在此单独微调")
        lbl_no_song.setStyleSheet("font-size: 12px; color: #6E7781; line-height: 1.4;")
        csl.addWidget(lbl_no_song)

    syncl.addWidget(card_cur_song)

    # 全局默认偏移
    syncl.addWidget(QLabel("全局默认偏移", styleSheet="font-size: 13px; font-weight: 600; color: #1B1F24;"))
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

    self._update_live_offset_preview()

    l.addWidget(card_sync)
    l.addStretch()
    return page


def _update_live_offset_preview(self):
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
        empty_lbl = QLabel("暂无单独配置的歌曲记录")
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

        btn_del = QPushButton("✕")
        apply_circle_btn(btn_del, 24)
        btn_del.setToolTip("移除此歌曲的单独配置")
        btn_del.clicked.connect(lambda _, k=song_key: self._remove_draft_song_offset(k))
        rl.addWidget(btn_del)

        self._custom_songs_container.addWidget(row_widget)


def _on_draft_song_offset_changed(self, song_key: str, val: int):
    self._song_offsets_draft[song_key] = val
    if self._current_title and hasattr(self, "_spin_song_off") and self._spin_song_off is not None:
        cur_key = settings.make_song_key(self._current_title, self._current_artist)
        if song_key == cur_key:
            self._spin_song_off.blockSignals(True)
            self._spin_song_off.setValue(val)
            self._spin_song_off.blockSignals(False)
            self._update_live_offset_preview()


def _remove_draft_song_offset(self, song_key: str):
    self._song_offsets_draft.pop(song_key, None)
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


def _reset_defaults(self):
    self._slider_op.setValue(85)
    self._spin_cur.setValue(28)
    self._spin_ctx.setValue(14)
    if hasattr(self, "_spin_fs_cur"):
        self._spin_fs_cur.setValue(38)
    if hasattr(self, "_spin_fs_ctx"):
        self._spin_fs_ctx.setValue(18)
    self._switch_trans.setChecked(True)
    self._switch_roma.setChecked(False)
    if hasattr(self, "_combo_sec_mode"):
        idx_sm = self._combo_sec_mode.findData("prefer_trans")
        if idx_sm >= 0:
            self._combo_sec_mode.setCurrentIndex(idx_sm)
    if hasattr(self, "_combo_fs_ctx_sec"):
        idx_fs = self._combo_fs_ctx_sec.findData("both")
        if idx_fs >= 0:
            self._combo_fs_ctx_sec.setCurrentIndex(idx_fs)
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
    self._apply_preset_draft("classic")


def _save_and_apply(self):
    font_manager.save_font_items(self._font_items)

    apps_raw = self._apps_edit.text()
    apps = [a.strip() for a in apps_raw.split(",") if a.strip()]
    settings.set_watched_apps(apps)
    settings.set_show_translation(self._switch_trans.isChecked())
    settings.set_show_romaji(self._switch_roma.isChecked())
    if hasattr(self, "_combo_sec_mode"):
        settings.set_secondary_mode(self._combo_sec_mode.currentData() or "prefer_trans")
    if hasattr(self, "_combo_fs_ctx_sec"):
        settings.set_fullscreen_context_secondary_mode(self._combo_fs_ctx_sec.currentData() or "both")
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
    if hasattr(self, "_switch_fs_prevent_sleep"):
        settings.set_fullscreen_prevent_sleep(self._switch_fs_prevent_sleep.isChecked())

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

    settings.set_theme_preset(self._draft_theme_preset)
    settings.set_theme_seed_color(self._draft_seed_color)
    settings.set_theme_colors(self._draft_theme_colors)

    self.accept()
