"""
scripts/build_nuitka.py — Nuitka 构建与打包脚本 (支持本地与 GitHub Actions)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_icon() -> str:
    assets_dir = os.path.join(PROJECT_ROOT, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    icon_path = os.path.join(assets_dir, "icon.ico")
    if os.path.exists(icon_path) and os.path.getsize(icon_path) > 0:
        return icon_path

    print("[Build] 正在自动生成应用程序图标 assets/icon.ico ...")
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(sys.argv)
        px = QPixmap(256, 256)
        px.fill(QColor(0, 0, 0, 0))

        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        grad = QLinearGradient(0, 0, 256, 256)
        grad.setColorAt(0.0, QColor(90, 80, 240))
        grad.setColorAt(1.0, QColor(240, 80, 150))
        p.setBrush(grad)
        p.setPen(QColor(255, 255, 255, 80))
        p.drawRoundedRect(16, 16, 224, 224, 64, 64)

        p.setPen(QColor(255, 255, 255))
        f = QFont("Segoe UI Symbol", 112)
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(px.rect(), int(Qt.AlignmentFlag.AlignCenter), "♫")
        p.end()

        px.save(icon_path, "ico")
        print(f"[Build] 图标已生成: {icon_path}")
    except Exception as e:
        print(f"[Build] 自动生成图标失败: {e}，将跳过设置图标")
        return ""
    return icon_path


def run_nuitka(clean: bool = False) -> str:
    """Nuitka 编译"""
    dist_dir = os.path.join(PROJECT_ROOT, "dist")
    build_dir = os.path.join(PROJECT_ROOT, "build")

    if clean:
        print("[Build] 正在清理旧构建产物...")
        for p in [dist_dir, build_dir]:
            if os.path.exists(p):
                shutil.rmtree(p, ignore_errors=True)

    icon_path = ensure_icon()

    main_script = os.path.join(PROJECT_ROOT, "main.py")

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--windows-console-mode=disable",
        "--enable-plugin=pyqt6",
        f"--output-dir={dist_dir}",
        "--output-filename=LyrikFlow.exe",
        "--assume-yes-for-downloads",
        "--windows-company-name=LyrikFlow",
        "--windows-product-name=LyrikFlow",
        "--windows-file-version=1.0.0.0",
        "--windows-product-version=1.0.0",
        '--windows-file-description=LyrikFlow - Desktop Floating Lyrics',
        "--include-package=core",
        "--include-package=gui",
        "--include-package=Crypto",
        "--include-package=yaml",
    ]

    # 图标
    if icon_path and os.path.exists(icon_path):
        cmd.append(f"--windows-icon-from-ico={icon_path}")

    # SMTC 依赖包
    if sys.version_info < (3, 13):
        cmd.append("--include-package=winsdk")
    else:
        cmd.append("--include-package=winrt")

    # 入口
    cmd.append(main_script)

    print("\n" + "=" * 60)
    print("[Build] 启动 Nuitka 编译:")
    print(" ".join(cmd))
    print("=" * 60 + "\n")

    subprocess.check_call(cmd, cwd=PROJECT_ROOT)

    # 寻找生成的 dist 目录
    possible_dirs = [
        os.path.join(dist_dir, "LyrikFlow.dist"),
        os.path.join(dist_dir, "main.dist"),
    ]
    target_dist = None
    for p in possible_dirs:
        if os.path.isdir(p):
            target_dist = p
            break

    if not target_dist:
        raise RuntimeError(f"未找到 Nuitka 输出目录，检查 {dist_dir}")

    # 重命名规范化为 dist/LyrikFlow
    final_app_dir = os.path.join(dist_dir, "LyrikFlow")
    if os.path.exists(final_app_dir) and os.path.abspath(final_app_dir) != os.path.abspath(target_dist):
        shutil.rmtree(final_app_dir, ignore_errors=True)
    if os.path.abspath(target_dist) != os.path.abspath(final_app_dir):
        os.rename(target_dist, final_app_dir)

    return final_app_dir


def stage_extra_files(app_dir: str) -> None:
    print(f"[Build] 正在分发静态资源: {app_dir}")

    # 1. config.example.yaml
    src_cfg_example = os.path.join(PROJECT_ROOT, "config.example.yaml")
    if os.path.exists(src_cfg_example):
        shutil.copy2(src_cfg_example, os.path.join(app_dir, "config.example.yaml"))

    # 2. README.md
    src_readme = os.path.join(PROJECT_ROOT, "README.md")
    if os.path.exists(src_readme):
        shutil.copy2(src_readme, os.path.join(app_dir, "README.md"))

    # 3. data/fonts 目录与可用字体
    dest_data_fonts = os.path.join(app_dir, "data", "fonts")
    os.makedirs(dest_data_fonts, exist_ok=True)

    src_fonts_dirs = [
        os.path.join(PROJECT_ROOT, "data", "fonts"),
        os.path.join(PROJECT_ROOT, "fonts"),
    ]
    copied_fonts = 0
    for sdir in src_fonts_dirs:
        if os.path.isdir(sdir):
            for fname in os.listdir(sdir):
                if fname.lower().endswith((".ttf", ".otf", ".ttc")):
                    src_f = os.path.join(sdir, fname)
                    dest_f = os.path.join(dest_data_fonts, fname)
                    if not os.path.exists(dest_f):
                        shutil.copy2(src_f, dest_f)
                        copied_fonts += 1

    print(f"[Build] 静态资源同步完成 (包含 {copied_fonts} 个本地字体文件)。")


def zip_directory(src_dir: str, zip_path: str) -> None:
    print(f"[Build] 正在打包压缩: {zip_path} ...")
    base_folder_name = os.path.basename(src_dir)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, os.path.dirname(src_dir))
                zf.write(full_path, rel_path)
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"[Build] 打包成功! 文件大小: {size_mb:.2f} MB")


def main():
    parser = argparse.ArgumentParser(description="LyrikFlow Nuitka 构建工具")
    parser.add_argument("--clean", action="store_true", help="构建前清理旧产物")
    parser.add_argument("--zip", action="store_true", default=True, help="编译完成后生成 ZIP 压缩包 (默认开启)")
    parser.add_argument("--no-zip", dest="zip", action="store_false", help="不生成 ZIP 压缩包")
    args = parser.parse_args()

    try:
        app_dir = run_nuitka(clean=args.clean)
        stage_extra_files(app_dir)

        if args.zip:
            zip_dest = os.path.join(PROJECT_ROOT, "dist", "LyrikFlow-Windows-x64.zip")
            zip_directory(app_dir, zip_dest)

        print("\n" + "=" * 60)
        print("LyrikFlow Nuitka 编译与打包完成")
        print(f"📁 应用目录: {app_dir}")
        if args.zip:
            print(f"📦 压缩分发文件: {zip_dest}")
        print("=" * 60 + "\n")

    except subprocess.CalledProcessError as e:
        print(f"\n[Build Error] 编译命令返回失败退出码: {e.returncode}", file=sys.stderr)
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n[Build Error] 打包过程发生异常: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
