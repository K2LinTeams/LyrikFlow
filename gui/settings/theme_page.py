"""
gui/settings/theme_page.py — 主题预设、Material Design 色彩生成与微调设置页面
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import color_theme, font_manager

from .styles import apply_pill_primary, build_dialog_stylesheet
from .widgets import ColorSwatchButton, KaraokePreviewLabel, LyricPreviewProgressBar, MD3Card, MD3Switch


def _create_theme_page(self) -> QWidget:
    page = QWidget()
    l = QVBoxLayout(page)
    l.setContentsMargins(0, 4, 0, 0)
    l.setSpacing(14)

    # 1. 预设配色方案卡片
    l.addWidget(self._create_theme_presets_card())

    # 2. Material Design 单颜色自动生成卡片
    l.addWidget(self._create_theme_md_generator_card())

    # 3. 实时歌词视觉预览卡片
    l.addWidget(self._create_theme_preview_card())

    # 4. 自定义色彩细节调整卡片
    l.addWidget(self._create_theme_details_card())

    # 初始化色阶与预览
    self._refresh_theme_ui()

    return page


def _create_theme_presets_card(self) -> QWidget:
    card = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
    cl = QVBoxLayout(card)
    cl.setContentsMargins(18, 14, 18, 14)
    cl.setSpacing(12)

    top_h = QHBoxLayout()
    v_title = QVBoxLayout()
    v_title.setSpacing(2)
    lbl_title = QLabel("色彩方案")
    lbl_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
    lbl_desc = QLabel("选择好看的配色方案吧")
    lbl_desc.setStyleSheet("font-size: 11px; color: #6E7781;")
    v_title.addWidget(lbl_title)
    v_title.addWidget(lbl_desc)
    top_h.addLayout(v_title)
    top_h.addStretch()
    cl.addLayout(top_h)

    grid = QGridLayout()
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(8)

    presets_items = list(color_theme.PRESET_THEMES.items())

    self._preset_buttons.clear()
    self._preset_dots.clear()
    for idx, (k, pinfo) in enumerate(presets_items):
        btn = QPushButton()
        btn.setFixedHeight(44)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bl = QHBoxLayout(btn)
        bl.setContentsMargins(12, 6, 12, 6)
        bl.setSpacing(8)

        lbl_name = QLabel(pinfo.get("name", k))
        lbl_name.setStyleSheet("font-size: 12px; font-weight: 600; background: transparent; border: none;")
        bl.addWidget(lbl_name)
        bl.addStretch()

        cols = self._draft_theme_colors if k == "custom" else pinfo.get("colors", {})
        dots = [
            cols.get("lyric_active", "#FFFFFF"),
            cols.get("lyric_secondary", "#C3E1FF"),
            cols.get("accent", "#78CDFF"),
        ]
        dot_frames = []
        for dot_col in dots:
            dot = QFrame()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(
                f"background-color: {dot_col}; border-radius: 5px; border: 1px solid rgba(0,0,0,0.18);"
            )
            bl.addWidget(dot)
            dot_frames.append(dot)

        self._preset_dots[k] = dot_frames
        btn.clicked.connect(lambda _, key=k: self._apply_preset_draft(key))
        self._preset_buttons[k] = btn

        row = idx // 2
        col = idx % 2
        grid.addWidget(btn, row, col)

    cl.addLayout(grid)
    return card


def _create_theme_md_generator_card(self) -> QWidget:
    card = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
    cl = QVBoxLayout(card)
    cl.setContentsMargins(18, 14, 18, 14)
    cl.setSpacing(10)

    v_title = QVBoxLayout()
    v_title.setSpacing(2)
    lbl_title = QLabel("配色生成")
    lbl_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
    lbl_desc = QLabel("可选取或输入任一基准色")
    lbl_desc.setStyleSheet("font-size: 11px; color: #6E7781;")
    v_title.addWidget(lbl_title)
    v_title.addWidget(lbl_desc)
    cl.addLayout(v_title)

    row_seed = QHBoxLayout()
    row_seed.setSpacing(10)

    lbl_seed = QLabel("种子颜色：")
    lbl_seed.setStyleSheet("font-size: 13px; font-weight: 600; color: #1B1F24;")
    row_seed.addWidget(lbl_seed)

    self._btn_seed_swatch = ColorSwatchButton(self._draft_seed_color, size=34)
    self._btn_seed_swatch.colorChanged.connect(self._on_seed_color_picked)
    row_seed.addWidget(self._btn_seed_swatch)

    self._edit_seed_hex = QLineEdit(self._draft_seed_color)
    self._edit_seed_hex.setFixedWidth(96)
    self._edit_seed_hex.setMaxLength(7)
    self._edit_seed_hex.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._edit_seed_hex.setStyleSheet("""
        QLineEdit {
            padding: 6px 10px;
            border-radius: 12px;
            font-size: 13px;
            font-weight: 600;
        }
    """)
    self._edit_seed_hex.textEdited.connect(self._on_seed_hex_edited)
    self._edit_seed_hex.editingFinished.connect(self._on_seed_hex_finished)
    row_seed.addWidget(self._edit_seed_hex)

    row_seed.addStretch()
    cl.addLayout(row_seed)

    return card


def _create_theme_preview_card(self) -> QWidget:
    card = MD3Card(bg="#111422", border="#262C42", radius=18)
    cl = QVBoxLayout(card)
    cl.setContentsMargins(20, 16, 20, 16)
    cl.setSpacing(10)

    lbl_song_info = QLabel("♫ 不可解 — 花谱")
    lbl_song_info.setStyleSheet("color: #8C96AB; font-size: 12px; font-weight: 500; background: transparent; border: none;")
    cl.addWidget(lbl_song_info)

    self._prev_cur_line = KaraokePreviewLabel(
        text="不可解で不完全な魔法",
        active_hex=self._draft_theme_colors.get("lyric_active", "#FFFFFF"),
        inactive_hex=self._draft_theme_colors.get("lyric_inactive", "#A0A8B8"),
        progress=0.52,
    )
    cl.addWidget(self._prev_cur_line)

    self._prev_progress = LyricPreviewProgressBar("#FFFFFF", "#A0E6FF")
    cl.addWidget(self._prev_progress)

    self._prev_trans_line = QLabel("不可解的、不完全的魔法")
    self._prev_trans_line.setStyleSheet("font-size: 13px; background: transparent; border: none; color: #C3E1FF;")
    cl.addWidget(self._prev_trans_line)

    self._prev_next_line = QLabel("名前のない花のような")
    self._prev_next_line.setStyleSheet("font-size: 13px; background: transparent; border: none; color: #A0A8B8;")
    cl.addWidget(self._prev_next_line)

    return card


def _create_theme_details_card(self) -> QWidget:
    card = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
    cl = QVBoxLayout(card)
    cl.setContentsMargins(18, 14, 18, 14)
    cl.setSpacing(12)

    v_title = QVBoxLayout()
    v_title.setSpacing(2)
    lbl_title = QLabel("自定义色彩")
    lbl_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
    lbl_desc = QLabel("高级选项 尝试自己的搭配吧")
    lbl_desc.setStyleSheet("font-size: 11px; color: #6E7781;")
    v_title.addWidget(lbl_title)
    v_title.addWidget(lbl_desc)
    cl.addLayout(v_title)

    roles = [
        ("lyric_active", "主要行"),
        ("lyric_inactive", "次要行"),
        ("lyric_secondary", "译文注音行"),
        ("progress_start", "进度条起始"),
        ("progress_end", "进度条结束"),
        ("accent", "辅助色"),
    ]

    self._color_editor_swatches.clear()
    self._color_editor_edits.clear()

    for key, name in roles:
        cur_col = self._draft_theme_colors.get(key, "#FFFFFF")

        row_frame = QFrame()
        row_frame.setStyleSheet("""
            QFrame {
                background: #F8FAFD;
                border: 1px solid #E1E8F5;
                border-radius: 12px;
            }
        """)
        rl = QHBoxLayout(row_frame)
        rl.setContentsMargins(16, 7, 16, 7)
        rl.setSpacing(12)

        lbl_rname = QLabel(name)
        lbl_rname.setStyleSheet("font-size: 13px; font-weight: 600; color: #1B1F24; background: transparent; border: none;")
        rl.addWidget(lbl_rname, 1)

        swatch = ColorSwatchButton(cur_col, size=32)
        swatch.colorChanged.connect(lambda hex_val, rk=key: self._on_color_swatch_changed(rk, hex_val))
        rl.addWidget(swatch)
        self._color_editor_swatches[key] = swatch

        edit = QLineEdit(cur_col)
        edit.setFixedWidth(96)
        edit.setMaxLength(7)
        edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        edit.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px;
                border-radius: 12px;
                font-size: 13px;
                font-weight: 600;
            }
        """)
        edit.textEdited.connect(lambda text, rk=key: self._on_color_hex_edited(rk, text))
        rl.addWidget(edit)
        self._color_editor_edits[key] = edit

        cl.addWidget(row_frame)

    return card


def _on_seed_color_picked(self, hex_val: str):
    self._draft_seed_color = hex_val.upper()
    if hasattr(self, "_edit_seed_hex"):
        self._edit_seed_hex.blockSignals(True)
        self._edit_seed_hex.setText(self._draft_seed_color)
        self._edit_seed_hex.blockSignals(False)
    self._generate_from_seed(self._draft_seed_color)


def _on_seed_hex_edited(self, text: str):
    text = text.strip()
    if len(text) == 7 and color_theme.is_valid_hex(text):
        normalized = color_theme.normalize_hex(text)
        self._draft_seed_color = normalized
        if hasattr(self, "_btn_seed_swatch"):
            self._btn_seed_swatch.set_color(normalized)
        self._generate_from_seed(normalized)


def _on_seed_hex_finished(self):
    if hasattr(self, "_edit_seed_hex"):
        val = self._edit_seed_hex.text().strip()
        if color_theme.is_valid_hex(val):
            normalized = color_theme.normalize_hex(val)
            self._edit_seed_hex.blockSignals(True)
            self._edit_seed_hex.setText(normalized)
            self._edit_seed_hex.blockSignals(False)
            if hasattr(self, "_btn_seed_swatch"):
                self._btn_seed_swatch.set_color(normalized)
            self._generate_from_seed(normalized)
        else:
            self._edit_seed_hex.blockSignals(True)
            self._edit_seed_hex.setText(self._draft_seed_color)
            self._edit_seed_hex.blockSignals(False)


def _generate_from_seed(self, seed_hex: str):
    seed_hex = color_theme.normalize_hex(seed_hex)
    self._draft_seed_color = seed_hex

    if hasattr(self, "_edit_seed_hex"):
        self._edit_seed_hex.blockSignals(True)
        self._edit_seed_hex.setText(seed_hex)
        self._edit_seed_hex.blockSignals(False)
    if hasattr(self, "_btn_seed_swatch"):
        self._btn_seed_swatch.set_color(seed_hex)

    scheme = color_theme.generate_md_color_scheme(seed_hex)
    lyrik_roles = scheme["lyrik_roles"]

    self._draft_theme_colors.update(lyrik_roles)
    self._draft_theme_preset = "custom"
    if "custom" in color_theme.PRESET_THEMES:
        color_theme.PRESET_THEMES["custom"]["colors"].update(self._draft_theme_colors)
        color_theme.PRESET_THEMES["custom"]["seed_color"] = seed_hex

    self._refresh_theme_ui()
    self._sync_dialog_theme()


def _apply_preset_draft(self, preset_key: str):
    preset = color_theme.get_preset(preset_key)
    self._draft_theme_preset = preset_key
    self._draft_seed_color = preset["seed_color"]
    self._draft_theme_colors = dict(preset["colors"])

    if hasattr(self, "_edit_seed_hex"):
        self._edit_seed_hex.blockSignals(True)
        self._edit_seed_hex.setText(self._draft_seed_color)
        self._edit_seed_hex.blockSignals(False)
    if hasattr(self, "_btn_seed_swatch"):
        self._btn_seed_swatch.set_color(self._draft_seed_color)

    self._refresh_theme_ui()
    self._sync_dialog_theme()


def _on_color_swatch_changed(self, role: str, new_hex: str):
    self._draft_theme_colors[role] = new_hex
    self._draft_theme_preset = "custom"
    if "custom" in color_theme.PRESET_THEMES:
        color_theme.PRESET_THEMES["custom"]["colors"][role] = new_hex
    if role in self._color_editor_edits:
        self._color_editor_edits[role].blockSignals(True)
        self._color_editor_edits[role].setText(new_hex)
        self._color_editor_edits[role].blockSignals(False)
    self._refresh_theme_preset_buttons()
    self._update_theme_preview()


def _on_color_hex_edited(self, role: str, text: str):
    if color_theme.is_valid_hex(text):
        normalized = color_theme.normalize_hex(text)
        self._draft_theme_colors[role] = normalized
        self._draft_theme_preset = "custom"
        if "custom" in color_theme.PRESET_THEMES:
            color_theme.PRESET_THEMES["custom"]["colors"][role] = normalized
        if role in self._color_editor_swatches:
            self._color_editor_swatches[role].set_color(normalized)
        self._refresh_theme_preset_buttons()
        self._update_theme_preview()


def _sync_dialog_theme(self):
    seed_hex = self._draft_seed_color or "#0B57D0"
    scheme = color_theme.generate_md_color_scheme(seed_hex)
    primary_hex = scheme["md3_light"]["primary"]
    container_hex = scheme["md3_light"]["primary_container"]
    self._current_primary_hex = primary_hex
    self._current_container_hex = container_hex

    font_css = font_manager.get_font_css_family(self._font_items)
    self.setStyleSheet(build_dialog_stylesheet(font_css, primary_hex, container_hex))

    if hasattr(self, "_icon_badge") and self._icon_badge:
        self._icon_badge.setStyleSheet(
            f"background: {container_hex}; color: {primary_hex}; border-radius: 20px; font-size: 20px; font-weight: bold;"
        )

    if hasattr(self, "_nav_buttons") and self._nav_buttons and hasattr(self, "_stack"):
        cur_idx = self._stack.currentIndex()
        for i, b in enumerate(self._nav_buttons):
            if i == cur_idx:
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

    if hasattr(self, "_btn_save") and self._btn_save:
        apply_pill_primary(self._btn_save, font_css, primary_hex)

    if hasattr(self, "_btn_reset") and self._btn_reset:
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

    if hasattr(self, "_lbl_op_val") and self._lbl_op_val:
        self._lbl_op_val.setStyleSheet(
            f"background: {container_hex}; color: {primary_hex}; border-radius: 12px; padding: 2px 10px; font-weight: bold; font-size: 12px;"
        )

    MD3Switch.set_global_active_color(primary_hex)
    for sw in self.findChildren(MD3Switch):
        sw.update()

    if hasattr(self, "_font_mode"):
        self._set_font_mode(self._font_mode)

    if hasattr(self, "_font_list_layout"):
        self._render_font_items()

    self._refresh_theme_preset_buttons()


def _refresh_theme_preset_buttons(self):
    font_css = font_manager.get_font_css_family(self._font_items)
    primary_hex = getattr(self, "_current_primary_hex", "#0B57D0")
    container_hex = getattr(self, "_current_container_hex", "#D3E3FD")

    if hasattr(self, "_preset_dots") and "custom" in self._preset_dots:
        active_col = self._draft_theme_colors.get("lyric_active", "#FFFFFF")
        sec_col = self._draft_theme_colors.get("lyric_secondary", "#C3E1FF")
        acc_col = self._draft_theme_colors.get("accent", "#78CDFF")
        summary_cols = [active_col, sec_col, acc_col]
        for dot, col_str in zip(self._preset_dots["custom"], summary_cols):
            dot.setStyleSheet(
                f"background-color: {col_str}; border-radius: 5px; border: 1px solid rgba(0,0,0,0.18);"
            )

    for k, btn in self._preset_buttons.items():
        is_active = (k == self._draft_theme_preset)
        if is_active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {container_hex};
                    border: 1.8px solid {primary_hex};
                    border-radius: 12px;
                    font-family: {font_css};
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #FFFFFF;
                    border: 1.2px solid #DCE3EE;
                    border-radius: 12px;
                    font-family: {font_css};
                }}
                QPushButton:hover {{
                    background-color: #F4F7FB;
                    border-color: {primary_hex};
                }}
            """)


def _update_theme_preview(self):
    if not hasattr(self, "_prev_cur_line"):
        return

    c_act = self._draft_theme_colors.get("lyric_active", "#FFFFFF")
    c_inact = self._draft_theme_colors.get("lyric_inactive", "#A0A8B8")
    c_sec = self._draft_theme_colors.get("lyric_secondary", "#C3E1FF")
    c_p1 = self._draft_theme_colors.get("progress_start", "#FFFFFF")
    c_p2 = self._draft_theme_colors.get("progress_end", "#A0E6FF")

    if isinstance(self._prev_cur_line, KaraokePreviewLabel):
        self._prev_cur_line.set_colors(c_act, c_inact)
    else:
        self._prev_cur_line.setStyleSheet(
            f"font-size: 20px; font-weight: bold; background: transparent; border: none; color: {c_act};"
        )
    self._prev_trans_line.setStyleSheet(
        f"font-size: 13px; background: transparent; border: none; color: {c_sec};"
    )
    self._prev_next_line.setStyleSheet(
        f"font-size: 13px; background: transparent; border: none; color: {c_inact};"
    )
    self._prev_progress.set_colors(c_p1, c_p2)


def _refresh_theme_ui(self):
    self._refresh_theme_preset_buttons()

    if hasattr(self, "_btn_seed_swatch"):
        self._btn_seed_swatch.set_color(self._draft_seed_color)
    if hasattr(self, "_edit_seed_hex"):
        self._edit_seed_hex.blockSignals(True)
        self._edit_seed_hex.setText(self._draft_seed_color)
        self._edit_seed_hex.blockSignals(False)

    for rk, swatch in self._color_editor_swatches.items():
        c = self._draft_theme_colors.get(rk, "#FFFFFF")
        swatch.set_color(c)
    for rk, edit in self._color_editor_edits.items():
        c = self._draft_theme_colors.get(rk, "#FFFFFF")
        edit.blockSignals(True)
        edit.setText(c)
        edit.blockSignals(False)

    self._update_theme_preview()
