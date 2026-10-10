"""
smtc_listener.py — SMTC 媒体会话监听器
"""
from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from PyQt6.QtCore import QThread, pyqtSignal

try:
    from core import settings
except ImportError:
    import settings


class SMTCListener(QThread):
    song_changed = pyqtSignal(str, str, bytes)   # title, artist, thumbnail_bytes
    playback_state_changed = pyqtSignal(bool)    # is_playing
    tick = pyqtSignal(int)                        # elapsed_ms

    # AppUserModelId 白名单；留空则监听全部会话
    WATCHED_APPS: list[str] = []

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_flag = False
        self._state_lock = threading.RLock()

        self._is_playing = False
        self._play_start_wall: float = 0.0      # 单调时钟基准
        self._offset_ms: int = 0                # 手动偏移
        self._elapsed_when_paused: int = 0      # 暂停时的进度
        self._last_title: str = ""
        self._last_artist: str = ""
        self._last_state: Optional[bool] = None
        self._has_native_timeline: bool = False
        self._native_duration_ms: int = 0
        self._startup_initialized: bool = False
        self._pending_play_baseline: bool = False

        # 会话与事件相关句柄
        self._manager: Any = None
        self._current_session: Any = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._prop_lock: Optional[asyncio.Lock] = None

        self._tok_mgr_curr: Any = None
        self._tok_mgr_sess: Any = None
        self._tok_pb: Any = None
        self._tok_prop: Any = None
        self._tok_tl: Any = None

    # ── 公共接口 ─────────────────────────────────────────────────────────────
    def set_offset(self, offset_ms: int) -> None:
        """设置时间偏移（毫秒）"""
        with self._state_lock:
            self._offset_ms = int(offset_ms)

    def get_offset(self) -> int:
        """获取当前时间偏移（毫秒）"""
        with self._state_lock:
            return self._offset_ms

    def adjust_offset(self, delta_ms: int) -> None:
        """调整时间偏移（毫秒）"""
        with self._state_lock:
            self._offset_ms += delta_ms

    def reset_offset(self) -> None:
        with self._state_lock:
            self._offset_ms = settings.get_effective_song_offset(self._last_title, self._last_artist)

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

        self._loop = asyncio.get_running_loop()
        tick_interval = 0.15       # 进度更新间隔
        watchdog_interval = 1.0   # 会话保查看门狗间隔

        manager = await MediaManager.request_async()
        self._manager = manager

        # 注册会话管理器事件
        try:
            self._tok_mgr_curr = manager.add_current_session_changed(self._on_manager_session_changed)
        except Exception:
            self._tok_mgr_curr = None
        try:
            self._tok_mgr_sess = manager.add_sessions_changed(self._on_manager_session_changed)
        except Exception:
            self._tok_mgr_sess = None

        # 初始挂载会话
        now = time.monotonic()
        initial_session = self._pick_session(manager)
        if initial_session:
            self._attach_session(initial_session, now)

        last_tick = time.monotonic()
        last_watchdog = time.monotonic()

        try:
            while not self._stop_flag:
                now = time.monotonic()

                # 定期检查会话变更
                if now - last_watchdog >= watchdog_interval:
                    last_watchdog = now
                    session = self._pick_session(manager)
                    if session != self._current_session:
                        self._attach_session(session, now)

                # 发射播放进度信号
                if now - last_tick >= tick_interval:
                    last_tick = now
                    elapsed = self._get_elapsed_ms()
                    self.tick.emit(elapsed)

                await asyncio.sleep(0.05)

        finally:
            self._detach_current_session()
            if self._manager:
                if self._tok_mgr_curr is not None:
                    try:
                        self._manager.remove_current_session_changed(self._tok_mgr_curr)
                    except Exception:
                        pass
                if self._tok_mgr_sess is not None:
                    try:
                        self._manager.remove_sessions_changed(self._tok_mgr_sess)
                    except Exception:
                        pass

    # ── 会话挂载与事件绑定 ───────────────────────────────────────────────────
    def _is_target(self, app_name: str) -> bool:
        watched_lower = [w.lower().strip() for w in self.WATCHED_APPS if w.strip()]
        if not watched_lower:
            return True
        name = (app_name or "").lower()
        return any(w in name for w in watched_lower)

    def _pick_session(self, manager):
        """挑选目标媒体会话"""
        try:
            current = manager.get_current_session()
            if current and self._is_target(current.source_app_user_model_id):
                return current

            sessions = manager.get_sessions()
            if sessions and sessions.size > 0:
                for i in range(sessions.size):
                    s = sessions.get_at(i)
                    if self._is_target(s.source_app_user_model_id):
                        return s
        except Exception:
            pass
        return None

    def _session_has_timestamps(self, session, tl=None) -> bool:
        if not session:
            return False
        app_id = (getattr(session, "source_app_user_model_id", "") or "").lower()
        if any(k in app_id for k in ("cloudmusic", "netease", "orpheus")):
            return False
        if tl is None:
            try:
                tl = session.get_timeline_properties()
            except Exception:
                tl = None
        end_s = self._td_to_seconds(getattr(tl, "end_time", None)) if tl else 0.0
        return end_s > 0.0

    def _detach_current_session(self) -> None:
        """注销当前会话的事件回调"""
        with self._state_lock:
            self._pending_play_baseline = False
        s = self._current_session
        if s:
            if self._tok_pb is not None:
                try:
                    s.remove_playback_info_changed(self._tok_pb)
                except Exception:
                    pass
                self._tok_pb = None

            if self._tok_prop is not None:
                try:
                    s.remove_media_properties_changed(self._tok_prop)
                except Exception:
                    pass
                self._tok_prop = None

            if self._tok_tl is not None:
                try:
                    s.remove_timeline_properties_changed(self._tok_tl)
                except Exception:
                    pass
                self._tok_tl = None

        self._current_session = None

    def _attach_session(self, session, now: float) -> None:
        """挂载新会话并注册原生 SMTC 事件"""
        self._detach_current_session()
        if not session:
            with self._state_lock:
                if self._is_playing:
                    self._is_playing = False
                    self._last_state = False
                    self.playback_state_changed.emit(False)
            return

        self._current_session = session

        try:
            self._tok_pb = session.add_playback_info_changed(self._on_playback_info_changed)
        except Exception:
            self._tok_pb = None

        try:
            self._tok_prop = session.add_media_properties_changed(self._on_media_properties_changed)
        except Exception:
            self._tok_prop = None

        try:
            self._tok_tl = session.add_timeline_properties_changed(self._on_timeline_properties_changed)
        except Exception:
            self._tok_tl = None

        self._check_playback_status(session, now)
        if self._loop and not self._loop.is_closed():
            self._loop.create_task(self._check_media_properties(session, now))
        with self._state_lock:
            cur_playing = self._is_playing
        self._sync_timeline(session, cur_playing)

    # ── WinRT 事件调度与回调处理 ─────────────────────────────────────────────
    def _dispatch_to_loop(self, callback, *args) -> None:
        loop = self._loop
        if loop and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(callback, *args)
            except RuntimeError:
                pass

    def _on_manager_session_changed(self, sender, args) -> None:
        self._dispatch_to_loop(self._handle_session_switch_request)

    def _handle_session_switch_request(self) -> None:
        if self._stop_flag or not self._manager:
            return
        now = time.monotonic()
        new_session = self._pick_session(self._manager)
        if new_session != self._current_session:
            self._attach_session(new_session, now)

    def _on_playback_info_changed(self, sender, args) -> None:
        self._dispatch_to_loop(self._handle_playback_info_changed, sender)

    def _handle_playback_info_changed(self, sender=None) -> None:
        if self._stop_flag or not self._current_session:
            return
        if sender is not None and sender != self._current_session:
            return
        now = time.monotonic()
        self._check_playback_status(self._current_session, now)
        with self._state_lock:
            cur_playing = self._is_playing
        self._sync_timeline(self._current_session, cur_playing)

    def _on_media_properties_changed(self, sender, args) -> None:
        self._dispatch_to_loop(self._handle_media_properties_changed, sender)

    def _handle_media_properties_changed(self, sender=None) -> None:
        if self._stop_flag or not self._current_session:
            return
        if sender is not None and sender != self._current_session:
            return
        now = time.monotonic()
        if self._loop and not self._loop.is_closed():
            self._loop.create_task(self._check_media_properties(self._current_session, now))

    def _on_timeline_properties_changed(self, sender, args) -> None:
        self._dispatch_to_loop(self._handle_timeline_properties_changed, sender)

    def _handle_timeline_properties_changed(self, sender=None) -> None:
        if self._stop_flag or not self._current_session:
            return
        if sender is not None and sender != self._current_session:
            return
        with self._state_lock:
            cur_playing = self._is_playing
        self._sync_timeline(self._current_session, cur_playing)

    # ── 状态处理与同步 ───────────────────────────────────────────────────────
    def _check_playback_status(self, session, now: float) -> None:
        try:
            pb = session.get_playback_info()
            if not pb:
                return
            st = pb.playback_status
            # 状态映射: 4 = Playing, 5 = Paused, 3 = Stopped, 0 = Closed, 2 = Changing
            is_playing = (st == 4)
        except Exception:
            return

        with self._state_lock:
            if self._last_state is None:
                self._last_state = is_playing
                self._is_playing = is_playing
                self._play_start_wall = now
                self._elapsed_when_paused = 0
                if not self._has_native_timeline:
                    self._pending_play_baseline = not is_playing
                self.playback_state_changed.emit(is_playing)
                return

            if not self._has_native_timeline:
                if is_playing:
                    if self._pending_play_baseline:
                        self._play_start_wall = now
                        self._elapsed_when_paused = 0
                        self._pending_play_baseline = False
                        self._is_playing = True
                        self._last_state = True
                        self.playback_state_changed.emit(True)
                        self.tick.emit(self._get_elapsed_ms_locked())
                        return
                    elif not self._is_playing:
                        self._play_start_wall = now - (self._elapsed_when_paused / 1000.0)
                        self._is_playing = True
                        self._last_state = True
                        self.playback_state_changed.emit(True)
                        self.tick.emit(self._get_elapsed_ms_locked())
                        return
                else:
                    if st == 2:
                        self._pending_play_baseline = True
                        self._elapsed_when_paused = 0
                    elif self._is_playing:
                        self._elapsed_when_paused = self._get_raw_elapsed_ms_locked()

                    if self._is_playing or st == 2:
                        self._is_playing = False
                        self._last_state = False
                        self.playback_state_changed.emit(False)
                        self.tick.emit(self._get_elapsed_ms_locked())
                    return

            if is_playing != self._last_state:
                self._last_state = is_playing
                if is_playing and not self._is_playing:
                    self._play_start_wall = now - (self._elapsed_when_paused / 1000.0)
                elif not is_playing and self._is_playing:
                    self._elapsed_when_paused = self._get_raw_elapsed_ms_locked()
                self._is_playing = is_playing
                self.playback_state_changed.emit(is_playing)

    async def _check_media_properties(self, session, now: float) -> None:
        if self._prop_lock is None:
            self._prop_lock = asyncio.Lock()
        async with self._prop_lock:
            if self._stop_flag or session != self._current_session:
                return
            try:
                props = await session.try_get_media_properties_async()
                if not props:
                    return
                title = (props.title or "").strip()
                artist = (props.artist or "").strip()
            except Exception:
                return

            if not title:
                return

            with self._state_lock:
                song_changed = (title != self._last_title or artist != self._last_artist)
                if not self._startup_initialized or song_changed:
                    self._startup_initialized = True
                    self._last_title = title
                    self._last_artist = artist
                    self._offset_ms = settings.get_effective_song_offset(title, artist)
                    self._elapsed_when_paused = 0

                    tl = None
                    try:
                        tl = session.get_timeline_properties()
                    except Exception:
                        pass
                    has_native = self._session_has_timestamps(session, tl)
                    self._has_native_timeline = has_native
                    end_s = self._td_to_seconds(getattr(tl, "end_time", None)) if tl else 0.0
                    self._native_duration_ms = int(end_s * 1000) if has_native else 0

                    pb = None
                    try:
                        pb = session.get_playback_info()
                    except Exception:
                        pass
                    st = pb.playback_status if pb else 0
                    is_currently_playing = (st == 4)

                    now_mono = time.monotonic()
                    if has_native:
                        self._pending_play_baseline = False
                        self._is_playing = is_currently_playing
                        self._last_state = is_currently_playing
                        self._play_start_wall = now_mono
                    else:
                        if is_currently_playing:
                            self._play_start_wall = now_mono
                            self._pending_play_baseline = False
                            self._is_playing = True
                            self._last_state = True
                        else:
                            self._play_start_wall = now_mono
                            self._pending_play_baseline = True
                            self._is_playing = False
                            self._last_state = False

                    emit_needed = True
                else:
                    emit_needed = False

            if emit_needed:
                # 必须先同步并校准真实时间轴基准，确保外部接收 song_changed 时读取到的 SMTC 时钟已处于准确状态
                with self._state_lock:
                    cur_playing = self._is_playing
                self._sync_timeline(session, cur_playing, song_just_changed=True)

                thumb_bytes = await self._fetch_thumbnail(props)
                self.song_changed.emit(title, artist, thumb_bytes)

    def _sync_timeline(self, session, is_playing: bool, song_just_changed: bool = False) -> None:
        """同步时间轴状态并校准时钟基准"""
        now_mono = time.monotonic()
        tl = None
        try:
            tl = session.get_timeline_properties()
        except Exception:
            pass

        pos_s = self._td_to_seconds(tl.position) if tl else 0.0
        end_s = self._td_to_seconds(tl.end_time) if tl else 0.0
        last_updated = getattr(tl, "last_updated_time", None) if tl else None

        with self._state_lock:
            # 探测当前会话是否提供有效时间轴
            has_native = self._session_has_timestamps(session, tl)
            self._has_native_timeline = has_native
            self._native_duration_ms = int(end_s * 1000) if has_native else 0

            if not has_native:
                # 无原生时间轴：使用本地单调时钟计时
                if song_just_changed:
                    self._elapsed_when_paused = 0
                    if is_playing and not self._pending_play_baseline:
                        self._play_start_wall = now_mono
                    self.tick.emit(self._get_elapsed_ms_locked())
                return

            # 原生时间轴
            native_current_s = pos_s
            if is_playing and last_updated and not song_just_changed and pos_s >= 3.0:
                age_s = self._get_age_seconds(last_updated)
                if 0.0 <= age_s <= 30.0:
                    native_current_s += age_s

            if end_s > 0.0:
                native_current_s = min(native_current_s, end_s)
            native_current_s = max(0.0, native_current_s)

            native_pos_ms = int(native_current_s * 1000)
            local_raw_ms = self._get_raw_elapsed_ms_locked()
            diff_ms = abs(native_pos_ms - local_raw_ms)

            # 切歌或进度偏移超过阈值时校准基准时钟
            if song_just_changed or diff_ms > 300:
                if is_playing:
                    self._play_start_wall = now_mono - native_current_s
                else:
                    self._elapsed_when_paused = native_pos_ms
                self.tick.emit(self._get_elapsed_ms_locked())

    # ── 内部辅助计算 ─────────────────────────────────────────────────────────
    def _get_raw_elapsed_ms_locked(self) -> int:
        if self._is_playing:
            elapsed = (time.monotonic() - self._play_start_wall) * 1000.0
            elapsed_int = max(0, int(elapsed))
            if self._has_native_timeline and self._native_duration_ms > 0:
                elapsed_int = min(elapsed_int, self._native_duration_ms)
            return elapsed_int
        paused_val = max(0, self._elapsed_when_paused)
        if self._has_native_timeline and self._native_duration_ms > 0:
            paused_val = min(paused_val, self._native_duration_ms)
        return paused_val

    def _get_raw_elapsed_ms(self) -> int:
        with self._state_lock:
            return self._get_raw_elapsed_ms_locked()

    def _get_elapsed_ms_locked(self) -> int:
        return self._get_raw_elapsed_ms_locked() + self._offset_ms

    def _get_elapsed_ms(self) -> int:
        with self._state_lock:
            return self._get_elapsed_ms_locked()

    @staticmethod
    def _td_to_seconds(td) -> float:
        if td is None:
            return 0.0
        if hasattr(td, "total_seconds"):
            return float(td.total_seconds())
        if hasattr(td, "duration"):
            return float(td.duration) / 10_000_000.0
        return 0.0

    @staticmethod
    def _get_age_seconds(dt) -> float:
        if not dt or not isinstance(dt, datetime):
            return 0.0
        try:
            now = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (now - dt).total_seconds()
        except Exception:
            return 0.0

    @staticmethod
    async def _fetch_thumbnail(props) -> bytes:
        try:
            try:
                from winsdk.windows.storage.streams import (
                    Buffer, DataReader, InputStreamOptions,
                )
            except ImportError:
                from winrt.windows.storage.streams import (
                    Buffer, DataReader, InputStreamOptions,
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
            try:
                return bytes(buf)
            except Exception:
                pass
            reader = DataReader.from_buffer(buf)
            ba = bytearray(buf.length)
            reader.read_bytes(ba)
            return bytes(ba)
        except Exception:
            return b""
