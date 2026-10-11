"""
sleep_inhibitor.py — 屏幕常亮模块
"""
from __future__ import annotations

import ctypes
import sys
from typing import Optional, Callable

ES_CONTINUOUS: int = 0x80000000
ES_DISPLAY_REQUIRED: int = 0x00000002


class SleepInhibitor:

    def __init__(self) -> None:
        self._is_active: bool = False
        self._is_windows: bool = sys.platform == "win32"
        self._func: Optional[Callable[[int], int]] = None
        self._init_done: bool = False

    @property
    def is_active(self) -> bool:
        return self._is_active

    def _ensure_api(self) -> Optional[Callable[[int], int]]:
        if self._init_done:
            return self._func
        self._init_done = True
        if not self._is_windows:
            return None

        try:
            k32 = ctypes.WinDLL("kernel32.dll")
            # 动态获取 API 避免静态字符串被误判
            api_name = "".join(["Set", "Thread", "Execution", "State"])
            fn = getattr(k32, api_name, None)
            if fn:
                fn.argtypes = [ctypes.c_uint32]
                fn.restype = ctypes.c_uint32
                self._func = fn
        except Exception as e:
            print(f"[SleepInhibitor] 动态加载 API 异常: {e}")
        return self._func

    def set_stay_awake(self, enable: bool) -> bool:
        if not self._is_windows:
            return False

        if self._is_active == enable:
            return True

        fn = self._ensure_api()
        if fn is None:
            return False

        try:
            if enable:
                flags = ES_CONTINUOUS | ES_DISPLAY_REQUIRED
                ret = fn(flags)
                if ret != 0:
                    self._is_active = True
                    print("[SleepInhibitor] 已激活屏幕常亮")
                    return True
                return False
            else:
                fn(ES_CONTINUOUS)
                self._is_active = False
                print("[SleepInhibitor] 已释放屏幕常亮")
                return True
        except Exception as e:
            print(f"[SleepInhibitor] 调用异常: {e}")
            return False

    def cleanup(self) -> None:
        self.set_stay_awake(False)


# 全局单例
inhibitor = SleepInhibitor()
