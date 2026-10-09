import sys
import os
import traceback

# 确保项目根目录位于 sys.path 首位
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# 捕获全局未处理异常，避免 PyQt 隐式静默退出
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    print("\n[CRITICAL ERROR] 未捕获异常发生:", file=sys.stderr)
    traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)

sys.excepthook = handle_exception

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase

from core import font_manager
from gui import LyricsWindow


def main():
    print("[LyrikFlow] 正在初始化应用...")
    app = QApplication(sys.argv)
    app.setApplicationName("LyrikFlow")
    app.setOrganizationName("LyrikFlow")
    app.setQuitOnLastWindowClosed(False)

    # 扫描并加载本地字体
    font_manager.scan_fonts()
    app.setFont(font_manager.make_app_font(10))

    window = LyricsWindow()
    app.aboutToQuit.connect(window.cleanup)

    print("[LyrikFlow] 应用启动成功，主事件循环已就绪。")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
