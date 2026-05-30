# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Cassiel Agent.

Build:
    pyinstaller cassiel-agent.spec

Output:
    dist/CassielAgent/  (directory mode for NiceGUI compatibility)
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ── Project root ──────────────────────────────────────────────
SPEC_DIR = Path(SPECPATH)
SRC_DIR = SPEC_DIR / "src"

# ── Analysis ──────────────────────────────────────────────────
a = Analysis(
    [str(SPEC_DIR / "run.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[
        # NiceGUI frontend assets (JS, CSS, Quasar)
        *collect_data_files("nicegui"),
        # Playwright browser driver (minimal; full browsers installed separately)
        *collect_data_files("playwright"),
        # Pydantic JSON schema files
        *collect_data_files("pydantic"),
        # Placeholder config / cookies — created at runtime if missing
        (str(SPEC_DIR / "config.json"), "."),
    ],
    hiddenimports=[
        # NiceGUI + Quasar
        *collect_submodules("nicegui"),
        "nicegui.elements",
        "nicegui.events",
        "nicegui.client",
        "nicegui.server",
        # Playwright
        *collect_submodules("playwright"),
        "playwright._impl",
        "playwright._impl._browser",
        "playwright._impl._page",
        # OpenAI-compatible SDKs
        "openai",
        "httpx",
        "httpcore",
        # Cassiel subpackages
        "cassiel",
        "cassiel.ui",
        "cassiel.ui.main",
        "cassiel.ui.search_form",
        "cassiel.ui.candidate_table",
        "cassiel.ui.invitation_preview",
        "cassiel.agent",
        "cassiel.agent.orchestrator",
        "cassiel.agent.roles",
        "cassiel.collector",
        "cassiel.collector.boss",
        "cassiel.evaluator",
        "cassiel.evaluator.filter",
        "cassiel.writer",
        "cassiel.writer.invitation",
        "cassiel.writer.sender",
        "cassiel.config",
        "cassiel.config.settings",
        "cassiel.llm",
        "cassiel.llm.providers",
        "cassiel.models",
        "cassiel.models.candidate",
        "cassiel.session",
        "cassiel.session.store",
        # Async / networking
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "starlette",
        "starlette.routing",
        "starlette.middleware",
        "anyio",
        "sniffio",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tests",
        "__pycache__",
        "pytest",
        "pytest_asyncio",
        "setuptools",
        "pip",
        "wheel",
        "tkinter",
        "unittest",
        "xmlrpc",
        "pydoc",
        "distutils",
    ],
    noarchive=False,
)

# ── PYZ (compressed archive) ─────────────────────────────────
pyz = PYZ(a.pure)

# ── EXE (directory mode — required for NiceGUI) ──────────────
# NiceGUI serves static files at runtime, so we use COLLECT (directory)
# instead of --onefile which would break asset loading.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CassielAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # windowed mode — no terminal window
    icon=None,              # TODO: add .ico when available
    argv_emulation=False,
)

# ── COLLECT (directory bundle) ────────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CassielAgent",
)
