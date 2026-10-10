"""
scripts/build_nuitka.py — Nuitka build and packaging
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
    """Execute Nuitka compilation."""
    dist_dir = os.path.join(PROJECT_ROOT, "dist")
    build_dir = os.path.join(PROJECT_ROOT, "build")

    if clean:
        print("[Build] Cleaning previous build artifacts...")
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
        "--windows-file-description=LyrikFlow - Desktop Floating Lyrics",
        "--include-package=core",
        "--include-package=gui",
        "--include-package=Crypto",
        "--include-package=yaml",
    ]

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

    # Locate output folder
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
        raise RuntimeError(f"Nuitka output directory not found in {dist_dir}")

    final_app_dir = os.path.join(dist_dir, "LyrikFlow")
    if os.path.exists(final_app_dir) and os.path.abspath(final_app_dir) != os.path.abspath(target_dist):
        shutil.rmtree(final_app_dir, ignore_errors=True)
    if os.path.abspath(target_dist) != os.path.abspath(final_app_dir):
        os.rename(target_dist, final_app_dir)

    return final_app_dir


def stage_extra_files(app_dir: str) -> None:
    """Copy runtime configuration examples, readme, and fonts."""
    print(f"[Build] Staging extra static resources to: {app_dir}")

    # 1. config.example.yaml
    src_cfg_example = os.path.join(PROJECT_ROOT, "config.example.yaml")
    if os.path.exists(src_cfg_example):
        shutil.copy2(src_cfg_example, os.path.join(app_dir, "config.example.yaml"))

    # 2. README.md
    src_readme = os.path.join(PROJECT_ROOT, "README.md")
    if os.path.exists(src_readme):
        shutil.copy2(src_readme, os.path.join(app_dir, "README.md"))

    # 3. data/fonts directory
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

    print(f"[Build] Staging completed ({copied_fonts} font files included).")


def zip_directory(src_dir: str, zip_path: str) -> None:
    """Compress directory into zip archive."""
    print(f"[Build] Creating ZIP archive: {zip_path} ...")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, os.path.dirname(src_dir))
                zf.write(full_path, rel_path)
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"[Build] ZIP created successfully! Size: {size_mb:.2f} MB")


def main():
    parser = argparse.ArgumentParser(description="LyrikFlow Nuitka Build Tool")
    parser.add_argument("--clean", action="store_true", help="Clean previous build artifacts before compilation")
    parser.add_argument("--zip", action="store_true", default=True, help="Create ZIP package after compilation (default: True)")
    parser.add_argument("--no-zip", dest="zip", action="store_false", help="Do not create ZIP package")
    args = parser.parse_args()

    try:
        app_dir = run_nuitka(clean=args.clean)
        stage_extra_files(app_dir)

        zip_dest = ""
        if args.zip:
            zip_dest = os.path.join(PROJECT_ROOT, "dist", "LyrikFlow-Windows-x64.zip")
            zip_directory(app_dir, zip_dest)

        print("\n" + "=" * 60)
        print("LyrikFlow Nuitka build and packaging succeeded!")
        print(f"Application directory: {app_dir}")
        if args.zip and zip_dest:
            print(f"ZIP package: {zip_dest}")
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
