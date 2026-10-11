"""
gui/settings/ui_page.py — 歌词显示与界面外观设置页面
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core import db_cache, font_manager, settings
from core.providers.base import SearchSongItem

from .styles import apply_chip, apply_chip_active, apply_pill_banner_btn
from .widgets import MD3Card, MD3Switch
from .workers import ApplyVersionWorker, SearchVersionWorker


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

    # 3. 歌词排印与字号卡片
    card_font = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
    fl = QVBoxLayout(card_font)
    fl.setContentsMargins(18, 14, 18, 14)
    fl.setSpacing(10)

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

    # 功能开关卡片：双语翻译
    card_trans = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
    trans_l = QHBoxLayout(card_trans)
    trans_l.setContentsMargins(18, 14, 18, 14)

    trans_v = QVBoxLayout()
    trans_v.setSpacing(2)
    lbl_trans_t = QLabel("显示双语翻译")
    lbl_trans_t.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
    lbl_trans_d = QLabel("获取歌词的译文字幕")
    lbl_trans_d.setStyleSheet("font-size: 11px; color: #6E7781;")
    lbl_trans_d.setWordWrap(True)
    trans_v.addWidget(lbl_trans_t)
    trans_v.addWidget(lbl_trans_d)
    trans_l.addLayout(trans_v, 1)

    self._switch_trans = MD3Switch()
    self._switch_trans.setChecked(settings.get_show_translation())
    self._switch_trans.toggled.connect(lambda _: self._refresh_preview_visibility())
    trans_l.addWidget(self._switch_trans)
    l.addWidget(card_trans)

    # 功能开关卡片：罗马音
    card_roma = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
    roma_l = QHBoxLayout(card_roma)
    roma_l.setContentsMargins(18, 14, 18, 14)

    roma_v = QVBoxLayout()
    roma_v.setSpacing(2)
    lbl_roma_t = QLabel("显示罗马音")
    lbl_roma_t.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
    lbl_roma_d = QLabel("获取歌词的注音字幕")
    lbl_roma_d.setStyleSheet("font-size: 11px; color: #6E7781;")
    lbl_roma_d.setWordWrap(True)
    roma_v.addWidget(lbl_roma_t)
    roma_v.addWidget(lbl_roma_d)
    roma_l.addLayout(roma_v, 1)

    self._switch_roma = MD3Switch()
    self._switch_roma.setChecked(settings.get_show_romaji())
    self._switch_roma.toggled.connect(lambda _: self._refresh_preview_visibility())
    roma_l.addWidget(self._switch_roma)
    l.addWidget(card_roma)

    # 功能卡片：悬浮窗副行偏好
    card_sec_mode = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
    sec_mode_l = QHBoxLayout(card_sec_mode)
    sec_mode_l.setContentsMargins(18, 14, 18, 14)

    sec_mode_v = QVBoxLayout()
    sec_mode_v.setSpacing(2)
    lbl_sec_mode_t = QLabel("副行显示偏好")
    lbl_sec_mode_t.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
    lbl_sec_mode_d = QLabel("悬浮窗副行内容的呈现方式")
    lbl_sec_mode_d.setStyleSheet("font-size: 11px; color: #6E7781;")
    lbl_sec_mode_d.setWordWrap(True)
    sec_mode_v.addWidget(lbl_sec_mode_t)
    sec_mode_v.addWidget(lbl_sec_mode_d)
    sec_mode_l.addLayout(sec_mode_v, 1)

    self._combo_sec_mode = QComboBox()
    self._combo_sec_mode.addItem("显示译文", "prefer_trans")
    self._combo_sec_mode.addItem("显示注音", "prefer_romaji")
    self._combo_sec_mode.addItem("组合显示", "both")

    cur_sec_mode = settings.get_secondary_mode()
    idx_sm = self._combo_sec_mode.findData(cur_sec_mode)
    if idx_sm >= 0:
        self._combo_sec_mode.setCurrentIndex(idx_sm)
    self._combo_sec_mode.currentIndexChanged.connect(lambda _: self._refresh_preview_visibility())
    sec_mode_l.addWidget(self._combo_sec_mode)
    l.addWidget(card_sec_mode)
    self._refresh_preview_visibility()

    # 全屏非当前行显示内容卡片
    card_fs_ctx_sec = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
    fs_ctx_sec_l = QHBoxLayout(card_fs_ctx_sec)
    fs_ctx_sec_l.setContentsMargins(18, 14, 18, 14)

    fs_ctx_sec_v = QVBoxLayout()
    fs_ctx_sec_v.setSpacing(2)
    lbl_fs_ctx_sec_t = QLabel("全屏非当前行显示内容")
    lbl_fs_ctx_sec_t.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
    lbl_fs_ctx_sec_d = QLabel("全屏模式的上下文呈现方式")
    lbl_fs_ctx_sec_d.setStyleSheet("font-size: 11px; color: #6E7781;")
    lbl_fs_ctx_sec_d.setWordWrap(True)
    fs_ctx_sec_v.addWidget(lbl_fs_ctx_sec_t)
    fs_ctx_sec_v.addWidget(lbl_fs_ctx_sec_d)
    fs_ctx_sec_l.addLayout(fs_ctx_sec_v, 1)

    self._combo_fs_ctx_sec = QComboBox()
    self._combo_fs_ctx_sec.addItem("仅主歌词", "none")
    self._combo_fs_ctx_sec.addItem("显示翻译", "translation")
    self._combo_fs_ctx_sec.addItem("显示注音", "romaji")
    self._combo_fs_ctx_sec.addItem("显示两者", "both")

    cur_fs_ctx_mode = settings.get_fullscreen_context_secondary_mode()
    idx_fs = self._combo_fs_ctx_sec.findData(cur_fs_ctx_mode)
    if idx_fs >= 0:
        self._combo_fs_ctx_sec.setCurrentIndex(idx_fs)
    fs_ctx_sec_l.addWidget(self._combo_fs_ctx_sec)
    l.addWidget(card_fs_ctx_sec)

    l.addStretch()

    # 标准歌词进度条
    card_prog = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
    prog_l = QHBoxLayout(card_prog)
    prog_l.setContentsMargins(18, 14, 18, 14)

    prog_v = QVBoxLayout()
    prog_v.setSpacing(2)
    lbl_prog_t = QLabel("标准歌词进度条")
    lbl_prog_t.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
    lbl_prog_d = QLabel("在标准歌词下方显示单句胶囊进度条")
    lbl_prog_d.setStyleSheet("font-size: 11px; color: #6E7781;")
    lbl_prog_d.setWordWrap(True)
    prog_v.addWidget(lbl_prog_t)
    prog_v.addWidget(lbl_prog_d)
    prog_l.addLayout(prog_v, 1)

    self._switch_progress = MD3Switch()
    self._switch_progress.setChecked(settings.get_show_line_progress())
    prog_l.addWidget(self._switch_progress)
    l.addWidget(card_prog)

    # 段落解析
    card_sec = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
    sec_l = QHBoxLayout(card_sec)
    sec_l.setContentsMargins(18, 14, 18, 14)

    sec_v = QVBoxLayout()
    sec_v.setSpacing(2)
    lbl_sec_t = QLabel("歌词段落解析")
    lbl_sec_t.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
    lbl_sec_d = QLabel("识别段落章节和角色名，显示在副行（如可能）")
    lbl_sec_d.setStyleSheet("font-size: 11px; color: #6E7781;")
    lbl_sec_d.setWordWrap(True)
    sec_v.addWidget(lbl_sec_t)
    sec_v.addWidget(lbl_sec_d)
    sec_l.addLayout(sec_v, 1)

    self._switch_sections = MD3Switch()
    self._switch_sections.setChecked(settings.get_parse_sections())
    sec_l.addWidget(self._switch_sections)
    l.addWidget(card_sec)

    # 全屏上下文行数
    card_fs = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
    fs_l = QVBoxLayout(card_fs)
    fs_l.setContentsMargins(18, 14, 18, 14)
    fs_l.setSpacing(10)

    lbl_fs_t = QLabel("全屏上下文显示行数")
    lbl_fs_t.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
    fs_l.addWidget(lbl_fs_t)

    lbl_fs_d = QLabel("当前高亮歌词上下各显示的行数")
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

    # 全屏播放防熄屏开关卡片
    card_fs_sleep = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
    fs_sleep_l = QHBoxLayout(card_fs_sleep)
    fs_sleep_l.setContentsMargins(18, 14, 18, 14)

    fs_sleep_v = QVBoxLayout()
    fs_sleep_v.setSpacing(2)
    lbl_fs_sleep_t = QLabel("屏幕常亮")
    lbl_fs_sleep_t.setStyleSheet("font-size: 14px; font-weight: 600; color: #1B1F24;")
    lbl_fs_sleep_d = QLabel("以全屏模式播放时将保持不熄屏")
    lbl_fs_sleep_d.setStyleSheet("font-size: 11px; color: #6E7781;")
    lbl_fs_sleep_d.setWordWrap(True)
    fs_sleep_v.addWidget(lbl_fs_sleep_t)
    fs_sleep_v.addWidget(lbl_fs_sleep_d)
    fs_sleep_l.addLayout(fs_sleep_v, 1)

    self._switch_fs_prevent_sleep = MD3Switch()
    self._switch_fs_prevent_sleep.setChecked(settings.get_fullscreen_prevent_sleep())
    fs_sleep_l.addWidget(self._switch_fs_prevent_sleep)
    l.addWidget(card_fs_sleep)

    return page


def _create_lyric_override_card(self) -> QWidget:
    card = MD3Card(bg="#FFFFFF", border="#E1E8F5", radius=18)
    cl = QVBoxLayout(card)
    cl.setContentsMargins(18, 16, 18, 16)
    cl.setSpacing(12)

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

    row_chips = QHBoxLayout()
    row_chips.setSpacing(8)
    row_chips.addWidget(QLabel("检索来源：", styleSheet="font-size: 11px; color: #6E7781;"))

    self._override_provider_filter = "all"
    self._provider_chips = {}
    providers = [("全部提供商", "all"), ("网易云音乐", "netease"), ("QQ 音乐", "qqmusic"), ("LRCLIB", "lrclib")]
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

    self._lbl_empty_results = QLabel("可点击上方搜索以获取可用来源")
    self._lbl_empty_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._lbl_empty_results.setStyleSheet("font-size: 12px; color: #8C939E; padding: 20px 0;")
    self._results_layout.addWidget(self._lbl_empty_results)
    self._results_layout.addStretch()

    self._results_scroll.setWidget(self._results_container)
    cl.addWidget(self._results_scroll)

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
    if self._all_search_results and kw == self._all_search_kw:
        if p_code == "all":
            filtered = list(self._all_search_results)
        else:
            filtered = [it for it in self._all_search_results if it.provider.lower() == p_code.lower()]
        self._displayed_search_results = filtered
        self._render_search_results(filtered)


def _get_current_lyric_info(self) -> tuple[str, str, str]:
    parsed = None
    prov = ""

    if getattr(self, "_active_applied_item", None):
        prov = self._active_applied_item.provider
        parsed = getattr(self, "_active_applied_parsed", None)

    if not parsed and self._current_title:
        cached = db_cache.get_song_cache(self._current_title, self._current_artist)
        if cached:
            parsed = cached.get("parsed")
            if not prov:
                prov = cached.get("provider") or (parsed.provider if parsed else "")

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
            self._active_applied_item
            and self._active_applied_item.provider.lower() == item.provider.lower()
            and (
                str(item.song_id) == str(self._active_applied_item.song_id)
                or (item.song_mid and item.song_mid == getattr(self._active_applied_item, "song_mid", ""))
                or (item.title == self._active_applied_item.title and item.artist == self._active_applied_item.artist)
            )
        )
        is_current = is_match_applied or bool(
            active_prov
            and item.provider.lower() == active_prov
            and (
                (active_song_id and str(item.song_id) == active_song_id)
                or (active_song_id and getattr(item, "song_mid", "") and str(item.song_mid) == active_song_id)
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
            if self._controller and hasattr(self._controller, "_reload_current_song_lyrics"):
                self._controller._reload_current_song_lyrics()
            self._refresh_override_status_badge()
            if self._displayed_search_results:
                self._render_search_results(self._displayed_search_results)
            elif self._last_search_results:
                self._render_search_results(self._last_search_results)
        else:
            btn.setText("选用此版本")
            btn.setEnabled(True)
            from PyQt6.QtWidgets import QMessageBox

            tip = ""
            if item.provider.lower() in ("qqmusic", "netease"):
                tip = "\n\n该条目暂未拥有歌词数据，尝试一下其他音源吧"
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
    primary_hex = getattr(self, "_current_primary_hex", "#0B57D0")
    container_hex = getattr(self, "_current_container_hex", "#D3E3FD")
    if mode == "fullscreen":
        if hasattr(self, "_panel_ov"):
            self._panel_ov.setVisible(False)
        if hasattr(self, "_panel_fs"):
            self._panel_fs.setVisible(True)
        if hasattr(self, "_btn_mode_fs"):
            self._btn_mode_fs.setStyleSheet(f"""
                QPushButton {{
                    background-color: {primary_hex};
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
                    background-color: {container_hex};
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
                    background-color: {primary_hex};
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
                    background-color: {container_hex};
                }}
            """)
    self._update_ui_preview()


def _update_ui_preview(self):
    active_families = [it.family for it in self._font_items if it.enabled and it.is_valid]
    mode = getattr(self, "_font_mode", "overlay")
    if mode == "fullscreen":
        raw_cur = self._spin_fs_cur.value() if hasattr(self, "_spin_fs_cur") else settings.get_fullscreen_font_size_current()
        cur_sz = max(12, int(raw_cur))
        sub_sz = max(10, int(cur_sz * 0.6))
        self._lbl_prev_cur.setFont(font_manager.make_app_font(cur_sz, bold=True, families=active_families))
        self._lbl_prev_roma.setFont(font_manager.make_app_font(sub_sz, bold=False, families=active_families))
        self._lbl_prev_trans.setFont(font_manager.make_app_font(sub_sz, bold=False, families=active_families))
    else:
        raw_cur = self._spin_cur.value() if hasattr(self, "_spin_cur") else settings.get_font_size_current()
        raw_ctx = self._spin_ctx.value() if hasattr(self, "_spin_ctx") else settings.get_font_size_context()
        cur_sz = max(12, int(raw_cur))
        ctx_sz = max(10, int(raw_ctx))
        self._lbl_prev_cur.setFont(font_manager.make_app_font(cur_sz, bold=True, families=active_families))
        self._lbl_prev_roma.setFont(font_manager.make_app_font(ctx_sz, bold=False, families=active_families))
        self._lbl_prev_trans.setFont(font_manager.make_app_font(ctx_sz, bold=False, families=active_families))
    self._refresh_preview_visibility()


def _refresh_preview_visibility(self):
    if not hasattr(self, "_lbl_prev_roma") or not hasattr(self, "_lbl_prev_trans"):
        return
    has_tr = self._switch_trans.isChecked() if hasattr(self, "_switch_trans") else settings.get_show_translation()
    has_ro = self._switch_roma.isChecked() if hasattr(self, "_switch_roma") else settings.get_show_romaji()
    mode = getattr(self, "_font_mode", "overlay")
    if mode == "fullscreen":
        self._lbl_prev_roma.setText("fu ka kai na, fu kan zen na ma hou")
        self._lbl_prev_roma.setVisible(has_ro)
        self._lbl_prev_trans.setText("不可解的、不完全的魔法")
        self._lbl_prev_trans.setVisible(has_tr)
    else:
        sec_mode = self._combo_sec_mode.currentData() if hasattr(self, "_combo_sec_mode") else settings.get_secondary_mode()
        if has_tr and has_ro:
            if sec_mode == "prefer_trans":
                self._lbl_prev_roma.setVisible(False)
                self._lbl_prev_trans.setText("不可解的、不完全的魔法")
                self._lbl_prev_trans.setVisible(True)
            elif sec_mode == "prefer_romaji":
                self._lbl_prev_roma.setText("fu ka kai na, fu kan zen na ma hou")
                self._lbl_prev_roma.setVisible(True)
                self._lbl_prev_trans.setVisible(False)
            else:  # "both"
                self._lbl_prev_roma.setText("fu ka kai na  ·  不可解的、不完全的魔法")
                self._lbl_prev_roma.setVisible(True)
                self._lbl_prev_trans.setVisible(False)
        else:
            self._lbl_prev_roma.setText("fu ka kai na, fu kan zen na ma hou")
            self._lbl_prev_trans.setText("不可解的、不完全的魔法")
            self._lbl_prev_trans.setVisible(has_ro)
            self._lbl_prev_trans.setVisible(has_tr)
