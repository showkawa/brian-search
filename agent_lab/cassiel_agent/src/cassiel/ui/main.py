"""NiceGUI主窗口 — Cassiel Agent 应用外壳

侧边栏导航 + 双页面架构:
- 招聘Agent: 4步Stepper工作流
- 账户配置: API Key + 外部凭据 + 搜索默认值
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from nicegui import ui

from cassiel.config.settings import AppConfig
from cassiel.ui.sidebar import Sidebar
from cassiel.ui.recruit_page import RecruitPage
from cassiel.ui.settings_page import SettingsPage


class AppShell:

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or self._load_config()
        self._sidebar: Sidebar | None = None

    def _load_config(self) -> AppConfig:
        try:
            cfg = AppConfig.from_json()
            if not cfg.api_keys.glm_key:
                cfg.api_keys.glm_key = os.getenv("GLM_API_KEY", "")
            if not cfg.api_keys.qwen_key:
                cfg.api_keys.qwen_key = os.getenv("QWEN_API_KEY", "")
            if not cfg.api_keys.deepseek_key:
                cfg.api_keys.deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
            return cfg
        except Exception:
            return AppConfig()

    def _build_ui(self) -> None:
        with ui.left_drawer(bordered=True, fixed=True).classes("w-[160px] q-pa-none") as drawer:
            self._sidebar = Sidebar(on_navigate=self._navigate)
            self._sidebar.build()

        with ui.column().classes("w-full q-pa-md"):
            self._tabs = ui.tabs().classes("hidden")
            with ui.tab_panels(self._tabs, value="recruit").classes("w-full") as self._panels:
                with ui.tab_panel("recruit"):
                    self._recruit_page = RecruitPage(self.config)
                    self._recruit_page.build()
                with ui.tab_panel("settings"):
                    self._settings_page = SettingsPage(self.config)
                    self._settings_page.build()

        self._schedule_startup_check()

    def _schedule_startup_check(self) -> None:

        async def _check() -> None:
            await asyncio.sleep(2)
            try:
                from cassiel.collector.boss_client import COOKIES_FILE
                if COOKIES_FILE.exists():
                    self._settings_page._update_boss_status()
            except Exception:
                pass

        ui.timer(0.1, _check, once=True)

    def _navigate(self, page_id: str) -> None:
        self._panels.set_value(page_id)

    def run(self, **kwargs: Any) -> None:
        self._build_ui()
        ui.run(
            native=True,
            title="Cassiel Agent — HRD 智能助手",
            port=8765,
            **kwargs,
        )


def run(**kwargs: Any) -> None:
    AppShell().run(**kwargs)
