"""
scripts/build_nuitka.py — Nuitka Build
"""
from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
import traceback
import zipfile

# Ensure UTF-8 output streams on Windows to prevent charmap encoding errors
if sys.platform == "win32":
    if sys.stdout and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_icon() -> str:
    """Ensure assets/icon.ico exists, generating it if necessary."""
    assets_dir = os.path.join(PROJECT_ROOT, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    icon_path = os.path.join(assets_dir, "icon.ico")
    if os.path.exists(icon_path) and os.path.getsize(icon_path) > 0:
        return icon_path

    print("[Build] Generating application icon assets/icon.ico...")
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
        print(f"[Build] Icon generated successfully: {icon_path}")
    except Exception as e:
        print(f"[Build Warning] Could not generate icon: {e}, proceeding without icon.")
        return ""
    return icon_path


def run_nuitka(clean: bool = False) -> str:
    dist_dir = os.path.join(PROJECT_ROOT, "dist")
    build_dir = os.path.join(PROJECT_ROOT, "build")

    if clean:
        print("[Build] Cleaning previous build artifacts...")
        for p in [dist_dir, build_dir]:
            if os.path.exists(p):
                shutil.rmtree(p, ignore_errors=True)

    os.makedirs(dist_dir, exist_ok=True)
    icon_path = ensure_icon()
    main_script = os.path.join(PROJECT_ROOT, "main.py")

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--onefile",
        "--windows-console-mode=disable",
        "--enable-plugin=pyqt6",
        f"--output-dir={dist_dir}",
        "--output-filename=LyrikFlow.exe",
        "--assume-yes-for-downloads",
        "--windows-company-name=LyrikFlow",
        "--windows-product-name=LyrikFlow",
        "--windows-file-version=1.0.0.0",
        "--windows-product-version=1.0.0",
        "--windows-file-description=LyrikFlow - Desktop Floating Lyrics",
        "--include-package=core",
        "--include-package=gui",
        "--include-package=Crypto",
        "--include-package=yaml",
    ]

    # Include config example file
    cfg_example = os.path.join(PROJECT_ROOT, "config.example.yaml")
    if os.path.exists(cfg_example):
        cmd.append(f"--include-data-file={cfg_example}=config.example.yaml")

    # Include fonts if present
    fonts_dir = os.path.join(PROJECT_ROOT, "data", "fonts")
    if os.path.isdir(fonts_dir) and any(os.scandir(fonts_dir)):
        cmd.append(f"--include-data-dir={fonts_dir}=data/fonts")

    if icon_path and os.path.exists(icon_path):
        cmd.append(f"--windows-icon-from-ico={icon_path}")

    if sys.version_info < (3, 13):
        cmd.append("--include-package=winsdk")
    else:
        cmd.append("--include-package=winrt")

    cmd.append(main_script)

    print("\n" + "=" * 60)
    print("[Build] Running Nuitka:")
    print(" ".join(cmd))
    print("=" * 60 + "\n")

    subprocess.check_call(cmd, cwd=PROJECT_ROOT)

    exe_path = os.path.join(dist_dir, "LyrikFlow.exe")
    if not os.path.exists(exe_path):
        raise RuntimeError(f"Expected binary not found: {exe_path}")

    return exe_path


def create_zip(exe_path: str, zip_path: str) -> None:
    """Create zip package containing the standalone executable and config example."""
    print(f"[Build] Creating ZIP package: {zip_path} ...")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(exe_path, "LyrikFlow.exe")
        cfg_example = os.path.join(PROJECT_ROOT, "config.example.yaml")
        if os.path.exists(cfg_example):
            zf.write(cfg_example, "config.example.yaml")
        readme = os.path.join(PROJECT_ROOT, "README.md")
        if os.path.exists(readme):
            zf.write(readme, "README.md")

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"[Build] ZIP created successfully! Size: {size_mb:.2f} MB")


def main():
    parser = argparse.ArgumentParser(description="LyrikFlow Nuitka Onefile Build Tool")
    parser.add_argument("--clean", action="store_true", help="Clean previous build artifacts before compilation")
    parser.add_argument("--zip", action="store_true", default=True, help="Create ZIP package after compilation (default: True)")
    parser.add_argument("--no-zip", dest="zip", action="store_false", help="Do not create ZIP package")
    args = parser.parse_args()

    try:
        exe_path = run_nuitka(clean=args.clean)
        exe_size_mb = os.path.getsize(exe_path) / (1024 * 1024)

        zip_dest = ""
        if args.zip:
            zip_dest = os.path.join(PROJECT_ROOT, "dist", "LyrikFlow-Windows-x64.zip")
            create_zip(exe_path, zip_dest)

        print("\n" + "=" * 60)
        print("LyrikFlow Nuitka Single-File Build Succeeded!")
        print(f"Portable Executable: {exe_path} ({exe_size_mb:.2f} MB)")
        if args.zip and zip_dest:
            print(f"ZIP Package: {zip_dest}")
        print("=" * 60 + "\n")

    except subprocess.CalledProcessError as e:
        print(f"\n[Build Error] Command returned non-zero exit code: {e.returncode}", file=sys.stderr)
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n[Build Error] Exception during build: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
