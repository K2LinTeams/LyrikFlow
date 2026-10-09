"""
lyrics_window.py — 主控制器
"""
from __future__ import annotations

import sys
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QImage, QPainter, QColor, QFont
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

try:
    from core import settings, db_cache, lyrics_fetcher, lyrics_parser
    from core.lyrics_parser import ParsedLyrics
    from core.smtc_listener import SMTCListener
    from gui.overlay_widget import OverlayWidget
    from gui.fullscreen_widget import FullscreenWidget
    from gui.settings_dialog import SettingsDialog
except ImportError:
    import settings
    import db_cache
    import lyrics_fetcher
    import lyrics_parser
    from lyrics_parser import ParsedLyrics
    from smtc_listener import SMTCListener
    from overlay_widget import OverlayWidget
    from fullscreen_widget import FullscreenWidget
    from settings_dialog import SettingsDialog


# ── 后台歌词获取线程 ──────────────────────────────────────────────────────────
class FetchThread(QThread):
    progress_changed = pyqtSignal(float)
    sub_name_ready   = pyqtSignal(str, str, str)          # (title, artist, sub_name)
    cover_ready      = pyqtSignal(str, str, object)       # (title, artist, hd_cover)
    done             = pyqtSignal(object, str, str, object, str)  # (lyrics, title, artist, hd_cover, sub_name)

    def __init__(self, title: str, artist: str, parent=None):
        super().__init__(parent)
        self._title  = title
        self._artist = artist
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        if self._is_cancelled:
            return
        self.progress_changed.emit(0.10)

        # 优先读取已存在的结构化缓存
        cached = db_cache.get_song_cache(self._title, self._artist)
        if cached and cached.get("parsed"):
            if self._is_cancelled:
                return
            self.progress_changed.emit(1.0)
            hd_cover = cached.get("hd_cover")
            sub_name = cached.get("sub_name", "")
            self.done.emit(cached["parsed"], self._title, self._artist, hd_cover, sub_name)
            return

        # 多源解析管线 (网易云 -> QQ音乐 -> LRCLIB)
        parsed, hd_cover, sub_name = lyrics_fetcher.fetch_lyrics_multi(
            title=self._title,
            artist=self._artist,
            on_progress=lambda p: self.progress_changed.emit(p),
            on_cover=lambda t, a, c: self.cover_ready.emit(t, a, c),
            on_sub_name=lambda t, a, s: self.sub_name_ready.emit(t, a, s),
            is_cancelled=lambda: self._is_cancelled,
        )

        if self._is_cancelled:
            return

        self.progress_changed.emit(1.0)
        self.done.emit(parsed, self._title, self._artist, hd_cover, sub_name)


# ── 主控制器 ──────────────────────────────────────────────────────────────────
class LyricsWindow(QObject):
    def __init__(self):
        super().__init__()

        self._mode: str = settings.get_mode()
        self._lyrics: Optional[ParsedLyrics] = None
        self._cur_index: int = -1
        self._current_title: str  = ""
        self._current_artist: str = ""
        self._thumb_bytes: bytes  = b""
        self._fetch_thread: Optional[FetchThread] = None

        # ── 创建 UI ──────────────────────────────────────────────────────
        self._overlay    = OverlayWidget(controller=self)
        self._fullscreen = FullscreenWidget(controller=self)

        # ── 系统托盘 ─────────────────────────────────────────────────────
        self._tray = self._setup_tray()

        # ── SMTC 监听 ─────────────────────────────────────────────────────
        self.smtc = SMTCListener()
        self.smtc.WATCHED_APPS = settings.get_watched_apps()
        self.smtc.song_changed.connect(self._on_song_changed)
        self.smtc.playback_state_changed.connect(self._on_playback_state)
        self.smtc.tick.connect(self._on_tick)
        self.smtc.start()

        # ── 初始显示（延迟一帧，确保 event loop 已启动）──────────────────
        QTimer.singleShot(0, self._apply_mode)

    # ── 模式切换 ─────────────────────────────────────────────────────────────
    def switch_mode(self, mode: str) -> None:
        self._mode = mode
        settings.set_mode(mode)
        self._apply_mode()

    def _apply_mode(self) -> None:
        if self._mode == "overlay":
            self._fullscreen.hide()
            self._overlay.show()
            self._overlay.raise_()
            self._overlay.activateWindow()
        else:
            self._overlay.hide()
            self._fullscreen.showFullScreen()
            self._fullscreen.raise_()
            self._fullscreen.activateWindow()
        self._push_lyrics_to_ui()

    # ── SMTC 信号处理 ─────────────────────────────────────────────────────────
    def _on_song_changed(self, title: str, artist: str, thumb_bytes: bytes) -> None:
        self._current_title  = title
        self._current_artist = artist
        self._cur_index      = -1

        # 初始化并应用此歌曲的有效偏移量
        effective_offset = settings.get_effective_song_offset(title, artist)
        self.smtc.set_offset(effective_offset)

        # 同步播放状态并重置进度
        is_playing = self.smtc._is_playing
        self._overlay.set_playing(is_playing)
        self._fullscreen.set_playing(is_playing)
        self._overlay.set_current_time(0, -1)
        self._fullscreen.set_current_time(0, -1)

        # 优先从本地数据库读取缓存
        cached = db_cache.get_song_cache(title, artist)
        if cached and cached.get("parsed"):
            if settings.get_song_offset(title, artist) is None and cached["parsed"].offset_ms != 0:
                self.smtc.set_offset(cached["parsed"].offset_ms)
            hd_cover = cached.get("hd_cover")
            sub_name = cached.get("sub_name", "")
            display_title = title
            display_artist = artist
            if sub_name and sub_name.lower() not in artist.lower() and sub_name.lower() not in title.lower():
                display_artist = f"{artist} · {sub_name}" if artist else sub_name

            self._thumb_bytes = hd_cover if (hd_cover and len(hd_cover) > 500) else thumb_bytes
            self._overlay.set_target_loading_progress(1.0)
            self._fullscreen.set_target_loading_progress(1.0)
            self._overlay.set_song(display_title, display_artist, self._thumb_bytes)
            self._fullscreen.set_song(display_title, display_artist, self._thumb_bytes)
            self._lyrics = cached["parsed"]
            self._overlay.set_status_text("")
            self._push_lyrics_to_ui()
            self._tray.setToolTip(f"LyrikFlow — {display_title}\n{display_artist}")
            return

        # 无缓存：优先展示 SMTC 原生封面，重置歌词并异步拉取高清内容与歌词
        self._thumb_bytes = bytes(thumb_bytes) if thumb_bytes else b""
        self._lyrics = None
        has_initial_cover = bool(self._thumb_bytes and len(self._thumb_bytes) > 100)
        self._overlay.reset_loading_progress(keep_cover=has_initial_cover)
        self._fullscreen.reset_loading_progress(keep_cover=has_initial_cover)
        self._overlay.set_song(title, artist, self._thumb_bytes)
        self._overlay.set_lyrics(None)
        self._fullscreen.set_song(title, artist, self._thumb_bytes)
        self._fullscreen.set_lyrics(None)

        # 后台异步获取歌词与高清封面并自动入库
        if self._fetch_thread and self._fetch_thread.isRunning():
            self._fetch_thread.cancel()
            self._fetch_thread.quit()
        self._fetch_thread = FetchThread(title, artist)
        self._fetch_thread.progress_changed.connect(self._on_fetch_progress)
        self._fetch_thread.sub_name_ready.connect(self._on_sub_name_ready)
        self._fetch_thread.cover_ready.connect(self._on_cover_ready)
        self._fetch_thread.done.connect(self._on_lyrics_fetched)
        self._fetch_thread.start()

        self._tray.setToolTip(f"LyrikFlow — {title}\n{artist}")

    def _on_playback_state(self, is_playing: bool) -> None:
        self._overlay.set_playing(is_playing)
        self._fullscreen.set_playing(is_playing)

    def _on_tick(self, elapsed_ms: int) -> None:
        if not self._lyrics:
            return
        idx = self._lyrics.get_line_index(elapsed_ms)
        self._cur_index = idx
        self._overlay.set_current_time(elapsed_ms, idx)
        self._fullscreen.set_current_time(elapsed_ms, idx)

    def _on_fetch_progress(self, val: float) -> None:
        self._overlay.set_target_loading_progress(val)
        self._fullscreen.set_target_loading_progress(val)

    def _on_sub_name_ready(self, title: str, artist: str, sub_name: str) -> None:
        if title != self._current_title or artist != self._current_artist:
            return
        if sub_name and sub_name.lower() not in artist.lower() and sub_name.lower() not in title.lower():
            display_artist = f"{artist} · {sub_name}" if artist else sub_name
            self._overlay.update_display_artist(display_artist)
            self._fullscreen.update_display_artist(display_artist)
            self._tray.setToolTip(f"LyrikFlow — {title}\n{display_artist}")

    def _on_cover_ready(self, title: str, artist: str, hd_cover: bytes) -> None:
        if title != self._current_title or artist != self._current_artist:
            return
        if hd_cover:
            self._thumb_bytes = bytes(hd_cover)
            self._overlay.update_hd_cover(hd_cover)
            self._fullscreen.update_hd_cover(hd_cover)
            self._overlay.set_target_loading_progress(1.0)
            self._fullscreen.set_target_loading_progress(1.0)

    def _on_lyrics_fetched(
        self,
        lyrics: Optional[ParsedLyrics],
        title: str,
        artist: str,
        hd_cover: Optional[bytes],
        sub_name: str = "",
    ) -> None:
        if title != self._current_title or artist != self._current_artist:
            return
        self._lyrics = lyrics

        # 将副名称（别名/翻译名称）拼接到歌手行
        display_title = title
        display_artist = artist
        if sub_name and sub_name.lower() not in artist.lower() and sub_name.lower() not in title.lower():
            display_artist = f"{artist} · {sub_name}" if artist else sub_name

        self._overlay.update_song_info(display_title, display_artist)
        self._fullscreen.update_song_info(display_title, display_artist)
        self._tray.setToolTip(f"LyrikFlow — {display_title}\n{display_artist}")

        if hd_cover and hd_cover != self._thumb_bytes:
            self._thumb_bytes = bytes(hd_cover)
            self._overlay.update_hd_cover(hd_cover)
            self._fullscreen.update_hd_cover(hd_cover)

        if lyrics:
            self._overlay.set_status_text("")
            if settings.get_song_offset(title, artist) is None and lyrics.offset_ms != 0:
                self.smtc.set_offset(lyrics.offset_ms)
        else:
            self._overlay.set_status_text(
                f"♪  {display_title}  —  {display_artist}  （暂无歌词）"
            )
        self._push_lyrics_to_ui()

    def _push_lyrics_to_ui(self) -> None:
        self._overlay.set_lyrics(self._lyrics)
        self._fullscreen.set_lyrics(self._lyrics)
        self._cur_index = -1

    # ── 设置对话框 ───────────────────────────────────────────────────────────
    def preview_offset(self, offset_ms: int) -> None:
        """设置对话框实时微调预览偏移量"""
        self.smtc.set_offset(offset_ms)
        if not self._lyrics:
            return
        current_ms = max(0, self.smtc._get_elapsed_ms())
        idx = self._lyrics.get_line_index(current_ms)
        self._cur_index = idx
        self._overlay.set_current_time(current_ms, idx)
        self._fullscreen.set_current_time(current_ms, idx)

    def open_settings(self) -> None:
        initial_opacity = settings.get_opacity()
        cover_bytes = self._thumb_bytes
        if not cover_bytes and self._current_title:
            cached = db_cache.get_song_cache(self._current_title, self._current_artist)
            if cached and cached.get("hd_cover"):
                cover_bytes = cached["hd_cover"]

        dlg = SettingsDialog(
            controller=self,
            overlay_widget=self._overlay,
            current_title=self._current_title,
            current_artist=self._current_artist,
            thumb_bytes=cover_bytes,
        )
        if dlg.exec():
            self.smtc.WATCHED_APPS = settings.get_watched_apps()
            effective_offset = settings.get_effective_song_offset(self._current_title, self._current_artist)
            self.smtc.set_offset(effective_offset)
            self._overlay.reload_settings()
            self._fullscreen.reload_settings()
            self._reload_current_song_lyrics()
        else:
            self._overlay.set_live_opacity(initial_opacity)
            initial_offset = settings.get_effective_song_offset(self._current_title, self._current_artist)
            self.preview_offset(initial_offset)

    def _reload_current_song_lyrics(self) -> None:
        """设置更新后重新解析当前歌曲歌词并即时推送到界面"""
        if not self._current_title:
            return
        effective_offset = settings.get_effective_song_offset(self._current_title, self._current_artist)
        self.smtc.set_offset(effective_offset)
        cached = db_cache.get_song_cache(self._current_title, self._current_artist)
        if cached and cached.get("parsed"):
            self._lyrics = cached["parsed"]
            hd_cover = cached.get("hd_cover")
            if hd_cover and len(hd_cover) > 500:
                self._thumb_bytes = bytes(hd_cover)
                self._overlay.update_hd_cover(hd_cover)
                self._fullscreen.update_hd_cover(hd_cover)
            self._overlay.set_status_text("")
            self._push_lyrics_to_ui()
            current_ms = max(0, self.smtc._get_elapsed_ms())
            if self._lyrics:
                idx = self._lyrics.get_line_index(current_ms)
                self._cur_index = idx
                self._overlay.set_current_time(current_ms, idx)
                self._fullscreen.set_current_time(current_ms, idx)
            self._overlay.update()
            self._fullscreen.update()

    # ── 系统托盘 ─────────────────────────────────────────────────────────────
    def _setup_tray(self) -> QSystemTrayIcon:
        # 绘制托盘图标 (64x64)
        icon_px = QPixmap(64, 64)
        icon_px.fill(QColor(0, 0, 0, 0))
        p = QPainter(icon_px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        from PyQt6.QtGui import QLinearGradient
        grad = QLinearGradient(0, 0, 64, 64)
        grad.setColorAt(0.0, QColor(90, 80, 240))
        grad.setColorAt(1.0, QColor(240, 80, 150))
        p.setBrush(grad)
        p.setPen(QColor(255, 255, 255, 80))
        p.drawRoundedRect(4, 4, 56, 56, 16, 16)

        p.setPen(QColor(255, 255, 255))
        f = QFont("Segoe UI Symbol", 28)
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(icon_px.rect(), int(Qt.AlignmentFlag.AlignCenter), "♫")
        p.end()

        app_icon = QIcon(icon_px)
        QApplication.instance().setWindowIcon(app_icon)

        tray = QSystemTrayIcon(app_icon, QApplication.instance())
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background:#181a2e; color:#eee;
                    border:1px solid #3a3d68; border-radius:8px; padding:6px; font-size: 13px; }
            QMenu::item { padding:6px 24px; border-radius:4px; }
            QMenu::item:selected { background:#3a3e78; color:#fff; }
        """)

        act_ov   = menu.addAction("🪟  悬浮条模式")
        act_fs   = menu.addAction("🖥  全画幅模式")
        menu.addSeparator()
        act_set  = menu.addAction("⚙️  设置…")
        menu.addSeparator()
        act_quit = menu.addAction("✖  退出")

        act_ov.triggered.connect(lambda: self.switch_mode("overlay"))
        act_fs.triggered.connect(lambda: self.switch_mode("fullscreen"))
        act_set.triggered.connect(self.open_settings)
        act_quit.triggered.connect(QApplication.quit)

        tray.setContextMenu(menu)
        tray.setToolTip("LyrikFlow — 桌面歌词")
        tray.activated.connect(self._on_tray_activated)
        tray.setVisible(True)
        tray.show()

        # 启动时弹窗提示，确认已运行
        tray.showMessage(
            "LyrikFlow 桌面歌词已启动",
            "已连接系统 SMTC 接口，开始播放后将自动显示歌词。\n• 鼠标拖拽移动\n• 滚轮调透明度\n• 双击切换全画幅",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )
        return tray

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self._mode == "overlay":
                if self._overlay.isVisible():
                    self._overlay.hide()
                else:
                    self._overlay.show()
                    self._overlay.raise_()

    def cleanup(self) -> None:
        self.smtc.stop()
        self.smtc.wait(2000)
