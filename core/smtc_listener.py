"""
smtc_listener.py — SMTC 媒体会话监听器
运行在独立 QThread 中，每 500ms 轮询一次会话状态。
发射信号：
  - song_changed(title, artist, thumbnail_bytes)  歌曲切换时
  - playback_state_changed(is_playing: bool)       播放/暂停切换时
  - tick(elapsed_ms: int)                          每 200ms，当前估算进度（毫秒）
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal


class SMTCListener(QThread):
    song_changed = pyqtSignal(str, str, bytes)   # title, artist, thumbnail_bytes
    playback_state_changed = pyqtSignal(bool)    # is_playing
    tick = pyqtSignal(int)                        # elapsed_ms (estimated)

    # AppUserModelId 白名单；留空 = 监听全部会话
    WATCHED_APPS: list[str] = []

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_flag = False
        self._is_playing = False
        self._play_start_wall: float = 0.0     # wall-clock 时间（秒）
        self._offset_ms: int = 0               # 用户手动偏移（毫秒）
        self._elapsed_when_paused: int = 0     # 暂停时保存的已过时间
        self._last_title: str = ""
        self._last_artist: str = ""
        self._last_state: Optional[bool] = None

    # ── 公共接口 ─────────────────────────────────────────────────────────────
    def adjust_offset(self, delta_ms: int) -> None:
        """由主线程调用，修改同步偏移量（正值 = 歌词提前，负值 = 歌词延后）"""
        self._offset_ms += delta_ms

    def reset_offset(self) -> None:
        self._offset_ms = 0

    def stop(self) -> None:
        self._stop_flag = True

    # ── 主循环 ───────────────────────────────────────────────────────────────
    def run(self) -> None:
        asyncio.run(self._main_loop())

    async def _main_loop(self) -> None:
        try:
            from winsdk.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as MediaManager,
            )
        except ImportError:
            from winrt.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as MediaManager,
            )


        poll_interval = 0.5       # 秒：会话状态轮询间隔
        tick_interval = 0.2       # 秒：进度 tick 间隔

        manager = await MediaManager.request_async()
        last_tick = time.monotonic()

        while not self._stop_flag:
            now = time.monotonic()

            # ── 轮询媒体会话 ─────────────────────────────────────────────
            try:
                session = self._pick_session(manager)
                if session:
                    await self._process_session(session)
                else:
                    # 没有会话时重置状态
                    if self._is_playing:
                        self._is_playing = False
                        self._last_state = False
                        self.playback_state_changed.emit(False)
            except Exception:
                pass

            # ── 进度 tick ────────────────────────────────────────────────
            if now - last_tick >= tick_interval:
                last_tick = now
                elapsed = self._get_elapsed_ms()
                self.tick.emit(max(0, elapsed))

            await asyncio.sleep(0.1)

    def _pick_session(self, manager):
        """从所有会话中挑选目标会话（根据白名单）"""
        try:
            sessions = manager.get_sessions()
            if not sessions or sessions.size == 0:
                return None

            watched_lower = [w.lower().strip() for w in self.WATCHED_APPS if w.strip()]

            def is_target(app_name: str) -> bool:
                if not watched_lower:
                    return True
                name = (app_name or "").lower()
                return any(w in name for w in watched_lower)

            # 优先检查当前活跃会话
            current = manager.get_current_session()
            if current and is_target(current.source_app_user_model_id):
                return current

            # 回退：遍历所有会话
            for i in range(sessions.size):
                s = sessions.get_at(i)
                if is_target(s.source_app_user_model_id):
                    return s
        except Exception:
            pass
        return None

    async def _process_session(self, session) -> None:
        # ── 媒体属性 ─────────────────────────────────────────────────────
        try:
            props = await session.try_get_media_properties_async()
            title  = (props.title  or "").strip()
            artist = (props.artist or "").strip()
        except Exception:
            return

        # ── 播放状态 ─────────────────────────────────────────────────────
        try:
            pb = session.get_playback_info()
            # playback_status: 4 = Playing, 5 = Paused, others = stopped
            is_playing = (pb.playback_status == 4)
        except Exception:
            is_playing = False

        # ── 歌曲切换检测 ─────────────────────────────────────────────────
        song_just_changed = (title != self._last_title or artist != self._last_artist)
        if song_just_changed and title:
            self._last_title  = title
            self._last_artist = artist
            self._offset_ms   = 0          # 新歌重置偏移
            self._elapsed_when_paused = 0
            # 若当前正在播放，重新计算起始时间
            if is_playing:
                self._play_start_wall = time.monotonic()
                self._is_playing = True
            # 读取封面缩略图
            thumb_bytes = await self._fetch_thumbnail(props)
            self.song_changed.emit(title, artist, thumb_bytes)

        # ── 播放状态变化检测 ─────────────────────────────────────────────
        if is_playing != self._last_state:
            self._last_state = is_playing
            if is_playing and not self._is_playing:
                # 由暂停→播放：记录新的起始时刻
                self._play_start_wall = time.monotonic() - (self._elapsed_when_paused / 1000.0)
            elif not is_playing and self._is_playing:
                # 由播放→暂停：保存已过时间
                self._elapsed_when_paused = self._get_elapsed_ms()
            self._is_playing = is_playing
            self.playback_state_changed.emit(is_playing)

        # 首次检测到歌曲且正在播放时初始化计时
        if song_just_changed and is_playing and title:
            self._play_start_wall = time.monotonic()

    def _get_elapsed_ms(self) -> int:
        """获取当前估算播放进度（毫秒）"""
        if self._is_playing:
            elapsed = (time.monotonic() - self._play_start_wall) * 1000
            return int(elapsed) + self._offset_ms
        else:
            return self._elapsed_when_paused + self._offset_ms

    @staticmethod
    async def _fetch_thumbnail(props) -> bytes:
        """从媒体属性中读取封面缩略图字节"""
        try:
            from winsdk.windows.storage.streams import (
                Buffer, DataReader, InputStreamOptions
            )
        except ImportError:
            from winrt.windows.storage.streams import (
                Buffer, DataReader, InputStreamOptions
            )
            thumb_ref = props.thumbnail
            if not thumb_ref:
                return b""
            stream = await thumb_ref.open_read_async()
            size = stream.size
            if size == 0:
                return b""
            buf = Buffer(size)
            await stream.read_async(buf, size, InputStreamOptions.READ_AHEAD)
            reader = DataReader.from_buffer(buf)
            return bytes([reader.read_byte() for _ in range(buf.length)])
        except Exception:
            return b""
