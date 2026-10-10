# LyrikFlow

**网易云音乐（其实不止兼容） SMTC 歌词悬浮小程序** — 自动同步当前播放歌曲的 LRC 歌词，支持半透明悬浮条和全画幅沉浸两种模式。

## 运行方式

```powershell
# 安装依赖
pip install PyQt6 PyQt6-Frameless-Window winsdk requests

# 启动
python main.py
```

## 使用前置条件

1. 打开**网易云音乐**，在 `设置 → 系统` 中勾选 **"开启 SMTC"**
2. 播放任意歌曲试试看
3. 启动 LyrikFlow，歌词条约 1~2 秒后出现

## 快捷键

| 快捷键 | 功能 |
|---|---|
| `←` | 歌词时间 -5 秒（歌词延后） |
| `→` | 歌词时间 +5 秒（歌词提前） |
| `F` | 悬浮条 → 全画幅 |
| `O` / `Esc` | 全画幅 → 悬浮条 |
| 鼠标滚轮 | 调整悬浮条透明度 |
| 右键 | 上下文菜单 |
| 托盘双击 | 显示/隐藏悬浮条 |

## 文件结构

```
LyrikFlow/
├── core/                  # 核心业务逻辑模块
│   ├── smtc_listener.py   # SMTC 媒体监听线程
│   ├── smtc_probe.py      # SMTC 调试探针
│   ├── lyrics_fetcher.py  # 歌词获取与多源聚合
│   ├── lyrics_parser.py   # LRC / YRC 逐字歌词解析器
│   ├── font_manager.py    # 字体扫描、优先级与回退栈
│   ├── db_cache.py        # SQLite 本地缓存管理
│   └── settings.py        # 用户偏好设置持久化
├── gui/                   # 图形界面组件
│   ├── lyrics_window.py   # 主控制器 & 托盘管理
│   ├── overlay_widget.py  # 半透明桌面悬浮歌词条
│   ├── fullscreen_widget.py# 全画幅沉浸式歌词组件
│   └── settings_dialog.py # MD3 风格设置面板
├── data/                  # 本地数据持久化目录
│   ├── fonts/             # 本地字体目录
│   └── lyrikflow_cache.db # SQLite 缓存数据库
├── main.py                # 程序入口
├── run.bat                # Windows 启动脚本
└── requirements.txt       # 项目依赖
```

## 已知限制

- 网易云音乐通过 SMTC **不暴露播放进度**，歌词同步靠本地计时器估算。
  快进后会有误差，因此不建议拖动进度条，校准请使用切歌。
- 网易云 API 获取失败时自动回退到 LRCLIB（英文歌曲覆盖更好）。
- 需要 **Python 3.9+ 64位（CPython）**，不支持 MSYS2 Python。

## 打包与发布 (Nuitka)

本项目已提供自动化构建脚本与 GitHub Actions 工作流：

### 本地编译 (Windows)

```powershell
pip install -r requirements.txt
pip install nuitka zstandard
python scripts/build_nuitka.py --clean --zip
```
编译产物位于 `dist/LyrikFlow` 目录及 `dist/LyrikFlow-Windows-x64.zip`。
