"""统一路径解析 — 配置文件 / Cookie / 数据库的位置

源码运行:
    <cassiel_agent>/config.json
    <cassiel_agent>/cookies.json
    <cassiel_agent>/data/cassiel.db

打包运行 (PyInstaller / Nuitka standalone):
    以上文件均放在可执行文件所在目录，便于安装后读写且不污染程序内部目录。
"""

from __future__ import annotations

import sys
from pathlib import Path


def _app_dir() -> Path:
    """返回应用数据目录

    - 源码运行: 项目目录 (含 pyproject.toml 的 cassiel_agent/)
    - 冻结运行: 可执行文件所在目录
    """
    if getattr(sys, "frozen", False):  # PyInstaller
        return Path(sys.executable).resolve().parent
    if "__compiled__" in globals():  # Nuitka standalone
        return Path(sys.executable).resolve().parent
    # src/cassiel/paths.py → 上溯 3 层即 cassiel_agent/
    return Path(__file__).resolve().parent.parent.parent


APP_DIR = _app_dir()

# ── 运行期文件 ──────────────────────────────────────────────
CONFIG_FILE = APP_DIR / "config.json"
COOKIES_FILE = APP_DIR / "cookies.json"
DATA_DIR = APP_DIR / "data"
DB_FILE = DATA_DIR / "cassiel.db"
