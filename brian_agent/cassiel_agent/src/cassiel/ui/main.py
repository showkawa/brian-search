"""NiceGUI主窗口 — Cassiel Agent 应用外壳

侧边栏导航 + 双页面架构:
- 招聘Agent: 4步Stepper工作流
- 账户配置: API Key + 外部凭据 + 搜索默认值
"""

from __future__ import annotations

import os
from typing import Any

from nicegui import ui

from cassiel.config.settings import AppConfig
from cassiel.ui.sidebar import Sidebar
from cassiel.ui.recruit_page import RecruitPage
from cassiel.ui.settings_page import SettingsPage


class AppShell:
    """Cassiel Agent 应用外壳

    管理侧边栏导航和页面切换。

    Usage:
        shell = AppShell()
        shell.run()
    """

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or self._load_config()
        self._sidebar: Sidebar | None = None

    def _load_config(self) -> AppConfig:
        """加载配置"""
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
        """构建应用 UI: 侧边栏 + 页面容器"""
        # ── 侧边栏 ──
        with ui.left_drawer(bordered=True, fixed=True).classes("w-[160px] q-pa-none") as drawer:
            self._sidebar = Sidebar(on_navigate=self._navigate)
            self._sidebar.build()

        # ── 页面内容区 ──
        with ui.column().classes("w-full q-pa-md"):
            # 使用 tab_panels 实现页面切换
            self._tabs = ui.tabs().classes("hidden")  # 隐藏的 tab 栏，仅做路由
            with ui.tab_panels(self._tabs, value="recruit").classes("w-full") as self._panels:
                with ui.tab_panel("recruit"):
                    self._recruit_page = RecruitPage(self.config)
                    self._recruit_page.build()
                with ui.tab_panel("settings"):
                    self._settings_page = SettingsPage(self.config)
                    self._settings_page.build()

    def _navigate(self, page_id: str) -> None:
        """侧边栏菜单点击 → 切换页面"""
        self._panels.set_value(page_id)

    def run(self, **kwargs: Any) -> None:
        """启动 NiceGUI 应用"""
        self._build_ui()
        ui.run(
            native=True,
            title="Cassiel Agent — HRD 智能助手",
            port=8765,
            **kwargs,
        )


def run(**kwargs: Any) -> None:
    """Module-level entry point for `cassiel-agent` console script."""
    AppShell().run(**kwargs)
