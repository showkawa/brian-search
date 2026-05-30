"""Cassiel Agent — Nuitka build script.

Usage:
    python build_nuitka.py          # build with defaults
    python build_nuitka.py --clean  # clean previous build first

Nuitka compiles Python to C and produces a standalone executable.
This is an alternative to PyInstaller that may yield better startup
performance and smaller distribution size.

Requirements:
    pip install nuitka ordered-set

Windows notes:
    - MSVC (recommended): Install Visual Studio Build Tools.
      Nuitka auto-detects MSVC and prefers it over MinGW.
    - MinGW64: Nuitka can download it automatically if MSVC is absent.
      MinGW builds may be slower and have subtle compatibility issues.

Playwright browsers:
    After building, install browsers into the dist directory:
        dist/CassielAgent/CassielAgent.exe playwright install chromium
    Or bundle them by adding --include-data-dir=... to the command.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
ENTRY_POINT = PROJECT_ROOT / "run.py"
OUTPUT_DIR = PROJECT_ROOT / "dist"
APP_NAME = "CassielAgent"

# Nuitka command-line arguments
NUITKA_BASE_ARGS = [
    sys.executable,
    "-m",
    "nuitka",
    # ── Output ──
    f"--output-dir={OUTPUT_DIR}",
    f"--output-filename={APP_NAME}",
    # ── Standalone (directory bundle, not --onefile) ──
    "--standalone",
    # ── Plugins ──
    "--enable-plugin=anti-bloat",       # remove unused stdlib modules
    # NiceGUI plugin — auto-detected if nuitka-plugin-nicegui is installed
    # "--enable-plugin=nicegui",
    # ── Windows ──
    "--windows-disable-console",        # no terminal window
    "--windows-icon-from-ico=None",     # TODO: add icon path
    # ── Optimization ──
    "--lto=yes",                        # link-time optimization
    "--assume-yes-for-downloads",       # auto-accept MinGW download
    # ── Inclusions ──
    "--include-package=nicegui",
    "--include-package=playwright",
    "--include-package=uvicorn",
    "--include-package=starlette",
    "--include-package=openai",
    "--include-package=httpx",
    "--include-package=pydantic",
    "--include-package=cassiel",
    # ── Exclusions (shrink bundle) ──
    "--nofollow-import-to=tests",
    "--nofollow-import-to=pytest",
    "--nofollow-import-to=pytest_asyncio",
    "--nofollow-import-to=tkinter",
    "--nofollow-import-to=unittest",
    "--nofollow-import-to=xmlrpc",
    "--nofollow-import-to=pydoc",
    "--nofollow-import-to=distutils",
    "--nofollow-import-to=setuptools",
    "--nofollow-import-to=pip",
    "--nofollow-import-to=wheel",
    # ── Entry point ──
    str(ENTRY_POINT),
]


def _check_nuitka() -> None:
    """Verify Nuitka is installed."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            capture_output=True,
            text=True,
        )
        print(f"Nuitka version: {result.stdout.strip()}")
    except FileNotFoundError:
        print(
            "ERROR: Nuitka is not installed.\n"
            "  pip install nuitka ordered-set",
            file=sys.stderr,
        )
        sys.exit(1)


def _clean() -> None:
    """Remove previous build artifacts."""
    dirs_to_clean = [
        OUTPUT_DIR,
        PROJECT_ROOT / "CassielAgent.build",
        PROJECT_ROOT / "CassielAgent.dist",
        PROJECT_ROOT / "CassielAgent.onefile-build",
    ]
    for d in dirs_to_clean:
        if d.exists():
            print(f"Removing {d} ...")
            shutil.rmtree(d, ignore_errors=True)


def build(clean: bool = False) -> None:
    """Run the Nuitka build."""
    _check_nuitka()

    if clean:
        _clean()

    cmd = NUITKA_BASE_ARGS.copy()

    # Check for nicegui nuitka plugin
    try:
        import nuitka_plugins  # noqa: F401 — just checking existence
        cmd.append("--enable-plugin=nicegui")
        print("NiceGUI Nuitka plugin detected — enabling.")
    except ImportError:
        print("NiceGUI Nuitka plugin not found — building without it.")
        print("  Install with: pip install nuitka-plugin-nicegui")

    print(f"\n{'=' * 60}")
    print(f"Building {APP_NAME} with Nuitka")
    print(f"Entry point: {ENTRY_POINT}")
    print(f"Output dir:  {OUTPUT_DIR}")
    print(f"{'=' * 60}\n")

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"\nERROR: Nuitka build failed (exit code {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)

    exe_path = OUTPUT_DIR / APP_NAME / f"{APP_NAME}.exe"
    print(f"\n{'=' * 60}")
    print(f"Build successful!")
    print(f"Executable: {exe_path}")
    print(f"{'=' * 60}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Cassiel Agent with Nuitka")
    parser.add_argument("--clean", action="store_true", help="Remove previous build artifacts")
    args = parser.parse_args()
    build(clean=args.clean)


if __name__ == "__main__":
    main()
