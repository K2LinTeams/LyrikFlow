"""
sleep_inhibitor.py — Windows 系统防休眠与防熄屏管理模块
"""
from __future__ import annotations

import ctypes
import sys

# Windows Execution State 标志位定义
ES_CONTINUOUS: int = 0x80000000
ES_SYSTEM_REQUIRED: int = 0x00000001
ES_DISPLAY_REQUIRED: int = 0x00000002


class SleepInhibitor:

    def __init__(self) -> None:
        self._is_active: bool = False
        self._is_windows: bool = sys.platform == "win32"
        self._set_thread_execution_state = None

        if self._is_windows:
            try:
                kernel32 = ctypes.windll.kernel32
                kernel32.SetThreadExecutionState.argtypes = [ctypes.c_uint32]
                kernel32.SetThreadExecutionState.restype = ctypes.c_uint32
                self._set_thread_execution_state = kernel32.SetThreadExecutionState
            except Exception as e:
                print(f"[SleepInhibitor] 初始化 Win32 API 失败: {e}")

    @property
    def is_active(self) -> bool:
        return self._is_active

    def set_stay_awake(self, enable: bool) -> bool:
        """设置是否阻止熄屏和系统睡眠。

        :param enable: True 为保持常亮防熄屏，False 为恢复系统电源计划。
        :return: 操作是否成功
        """
        if not self._is_windows or self._set_thread_execution_state is None:
            return False

        if self._is_active == enable:
            return True

        try:
            if enable:
                flags = ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
                ret = self._set_thread_execution_state(flags)
                if ret != 0:
                    self._is_active = True
                    print("[SleepInhibitor] 已激活防熄屏与防睡眠 (全屏播放中)")
                    return True
                else:
                    print("[SleepInhibitor] SetThreadExecutionState 调用返回 0，未生效")
                    return False
            else:
                ret = self._set_thread_execution_state(ES_CONTINUOUS)
                self._is_active = False
                print("[SleepInhibitor] 已释放防熄屏 (恢复系统电源策略)")
                return True
        except Exception as e:
            print(f"[SleepInhibitor] 调用 SetThreadExecutionState 异常: {e}")
            return False

    def cleanup(self) -> None:
        """应用退出时安全重置电源状态"""
        self.set_stay_awake(False)


# 全局单例
inhibitor = SleepInhibitor()
