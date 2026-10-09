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
from datetime import datetime, timezone
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
        self._elapsed_when_paused: int = 0     # 暂停时保存的已过时间（毫秒）
        self._last_title: str = ""
        self._last_artist: str = ""
        self._last_state: Optional[bool] = None
        self._has_native_timeline: bool = False # 当前会话是否支持原生 SMTC 时间轴

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
            self._has_native_timeline = False
            # 切歌默认视为开始播放：重置计时基准并广播播放状态，彻底解决从暂停冷启动切歌失步问题
            self._play_start_wall = time.monotonic()
            self._is_playing = True
            self._last_state = True
            self.playback_state_changed.emit(True)

            # 读取封面缩略图
            thumb_bytes = await self._fetch_thumbnail(props)
            self.song_changed.emit(title, artist, thumb_bytes)

        # ── 播放状态变化检测 ─────────────────────────────────────────────
        elif is_playing != self._last_state:
            self._last_state = is_playing
            if is_playing and not self._is_playing:
                # 由暂停→播放：记录新的起始时刻
                self._play_start_wall = time.monotonic() - (self._elapsed_when_paused / 1000.0)
            elif not is_playing and self._is_playing:
                # 由播放→暂停：保存已过时间
                self._elapsed_when_paused = self._get_raw_elapsed_ms()
            self._is_playing = is_playing
            self.playback_state_changed.emit(is_playing)

        # ── 原生 SMTC 时间轴自适应同步与 Seek 校准 ────────────────────────
        self._sync_timeline(session, is_playing, song_just_changed)

    def _sync_timeline(self, session, is_playing: bool, song_just_changed: bool) -> None:
        """
        自适应时间轴同步：
        - 若播放器支持 SMTC 原生时间轴（如 Spotify、系统播放器、QQ音乐等），实时校准播放进度和检测 Seek；
        - 若播放器为特例（如网易云音乐，不汇报时间轴），则平滑降级，保持本地单调时钟估算。
        """
        if song_just_changed:
            self._has_native_timeline = False

        try:
            tl = session.get_timeline_properties()
            if not tl:
                return

            pos_s = self._td_to_seconds(tl.position)
            end_s = self._td_to_seconds(tl.end_time)
            last_updated = tl.last_updated_time
        except Exception:
            return

        # ── 1. 自适应检测当前播放器是否有效支持 SMTC 原生时间轴 ──
        if not self._has_native_timeline:
            # 严格依据位置是否有效推进 (> 0.3s) 进行检测
            # 绝不能依据 end_s > 0 判断，因为网易云音乐等客户端汇报总时长但 pos 恒为 0，会导致本地时钟被死循环置零
            if pos_s > 0.3:
                self._has_native_timeline = True

        if not self._has_native_timeline:
            # 播放器不提供时间轴（如网易云音乐），平滑走本地估算时钟
            return

        # ── 2. 计算当前原生进度 ──
        native_current_s = pos_s
        if is_playing and last_updated:
            age_s = self._get_age_seconds(last_updated)
            if 0.0 <= age_s <= 30.0:
                native_current_s += age_s

        if end_s > 0.0:
            native_current_s = min(native_current_s, end_s)
        native_current_s = max(0.0, native_current_s)

        # ── 3. 进度对比与自适应校准 ──
        native_pos_ms = int(native_current_s * 1000)
        local_raw_ms = self._get_raw_elapsed_ms()
        diff_ms = abs(native_pos_ms - local_raw_ms)

        # 校准阈值：
        # - diff_ms > 1500ms：用户拖动了进度条 (Seek) 或大跨度跳跃，立即强对齐
        # - 500ms < diff_ms <= 1500ms：时钟累积漂移，平滑更新参考基准
        # - diff_ms <= 500ms：微小偏差，交由本地高精度计时器驱动，避免高频细微抖动
        if diff_ms > 500:
            if is_playing:
                self._play_start_wall = time.monotonic() - native_current_s
            else:
                self._elapsed_when_paused = native_pos_ms
                self.tick.emit(max(0, self._get_elapsed_ms()))

    def _get_raw_elapsed_ms(self) -> int:
        """获取当前纯播放进度估算值（不含用户手动偏移，毫秒）"""
        if self._is_playing:
            elapsed = (time.monotonic() - self._play_start_wall) * 1000
            return max(0, int(elapsed))
        else:
            return max(0, self._elapsed_when_paused)

    def _get_elapsed_ms(self) -> int:
        """获取当前有效播放进度（含用户手动偏移，毫秒）"""
        return self._get_raw_elapsed_ms() + self._offset_ms

    @staticmethod
    def _td_to_seconds(td) -> float:
        """安全转换 timedelta 或 Windows TimeSpan 到秒数浮点数"""
        if td is None:
            return 0.0
        if hasattr(td, "total_seconds"):
            return float(td.total_seconds())
        if hasattr(td, "duration"):
            return float(td.duration) / 10_000_000.0
        return 0.0

    @staticmethod
    def _get_age_seconds(dt) -> float:
        """计算 last_updated_time 距离当下的秒数"""
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
        """从媒体属性中读取封面缩略图字节"""
        try:
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
