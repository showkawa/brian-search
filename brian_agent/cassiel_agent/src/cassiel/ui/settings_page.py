"""账户配置页面 — API Key + 外部凭据 + 搜索默认值"""

from __future__ import annotations

import asyncio

from nicegui import ui

from cassiel.config.settings import AppConfig, SearchConfig, CredentialEntry
from cassiel.llm.providers import create_provider

# 下拉选项常量 (与 search_form.py 保持一致)
_EXPERIENCE_OPTIONS = ["不限", "1-3年", "3-5年", "5-10年", "10年以上"]
_EDUCATION_OPTIONS = ["不限", "大专", "本科", "硕士", "博士"]
_DEFAULT_SEARCH = SearchConfig()
_CITY_NAMES = list(_DEFAULT_SEARCH.CITY_CODES.keys())


class SettingsPage:
    """账户配置页面

    三个区块:
    1. 大模型 API — Key 输入 + 连接测试
    2. 外部网站凭据 — BOSS 直聘 Cookie 登录等
    3. 搜索默认值 — 城市/薪资/经验/学历/页数
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._model_selects: dict[str, ui.select] = {}
        self._model_checkboxes: dict[str, list[ui.checkbox]] = {}
        self._model_checklist_container: dict[str, ui.element] = {}
        self._model_checklist_column: dict[str, ui.column] = {}
        self._model_timestamp: dict[str, ui.label] = {}
        self._model_status: dict[str, ui.label] = {}
        self._model_hint: dict[str, ui.label] = {}
        self._prev_keys: dict[str, str] = {}

    def build(self) -> None:
        """构建配置页面 UI"""
        ui.label("⚙️ 账户配置").classes("text-h5 q-mb-md")

        self._build_api_keys_section()
        self._build_credentials_section()
        self._build_search_defaults_section()

    # ── 大模型 API ─────────────────────────────────────────────

    def _build_api_keys_section(self) -> None:
        with ui.card().classes("w-full q-mb-md"):
            ui.label("🤖 大模型 API").classes("text-subtitle1 q-mb-md text-primary")

            providers = [
                ("glm", "智谱 GLM", self.config.api_keys.glm_key),
                ("qwen", "通义 Qwen", self.config.api_keys.qwen_key),
                ("deepseek", "DeepSeek", self.config.api_keys.deepseek_key),
            ]

            self._key_inputs: dict[str, ui.input] = {}
            self._key_status: dict[str, ui.label] = {}

            for provider_id, label, default_key in providers:
                self._prev_keys[provider_id] = default_key

                # 第一行: Key + 测试按钮 + 状态
                with ui.row().classes("w-full items-center gap-4"):
                    ui.label(label).classes("w-24 text-body2 text-grey-7")
                    key_input = ui.input(
                        value=default_key,
                        password=True,
                        placeholder="sk-...",
                        on_change=lambda pid=provider_id: self._on_key_change(pid),
                    ).classes("flex-1").props("outlined dense")
                    status_label = ui.label("").classes("text-caption w-20")
                    ui.button(
                        "测试连接",
                        on_click=lambda pid=provider_id: self._test_connection(pid),
                    ).props("flat dense color=primary")

                    self._key_inputs[provider_id] = key_input
                    self._key_status[provider_id] = status_label

                    if default_key:
                        status_label.text = "✓ 已配置"
                        status_label.classes("text-positive", remove="text-grey-5")
                    else:
                        status_label.text = "未配置"
                        status_label.classes("text-grey-5")

                # 第二行: 模型拉取状态提示
                with ui.row().classes("w-full items-center gap-4"):
                    ui.label("").classes("w-24")
                    model_status = ui.label("").classes("text-caption text-grey-5")
                    self._model_status[provider_id] = model_status

                # 第三行: 提示文字
                with ui.row().classes("w-full items-center gap-4 q-mb-xs"):
                    ui.label("").classes("w-24")
                    hint_label = ui.label("").classes("text-caption")
                    self._model_hint[provider_id] = hint_label

                # 默认模型下拉
                with ui.row().classes("w-full items-center gap-4 q-mb-sm"):
                    ui.label("").classes("w-24")
                    enabled_models = self.config.enabled_models.get(provider_id, [])
                    current_model_name = (
                        self.config.model.search_model if provider_id == "glm" else
                        self.config.model.evaluate_model if provider_id == "deepseek" else
                        self.config.model.write_model
                    )
                    current_value = current_model_name if current_model_name in enabled_models else (enabled_models[0] if enabled_models else "")
                    model_select = ui.select(
                        label="默认模型",
                        options=[],
                        value=current_value,
                        on_change=lambda e, pid=provider_id: self._on_model_select_change(pid),
                    ).classes("w-56").props("outlined dense")
                    self._model_selects[provider_id] = model_select

                # checklist 容器（默认隐藏）
                checklist_container = ui.element("div").classes("w-full q-ml-24 q-mb-sm")
                checklist_container.set_visibility(False)
                self._model_checklist_container[provider_id] = checklist_container

                with checklist_container:
                    with ui.row().classes("w-full items-center gap-2 q-mb-xs"):
                        ui.button("全选", on_click=lambda pid=provider_id: self._select_all(pid)).props("flat dense size=sm")
                        ui.button("取消全选", on_click=lambda pid=provider_id: self._deselect_all(pid)).props("flat dense size=sm")

                    self._model_checklist_column[provider_id] = ui.column().classes("w-full")
                    self._model_checkboxes[provider_id] = []

                    timestamp = ui.label("").classes("text-caption text-grey-5")
                    self._model_timestamp[provider_id] = timestamp

                # 初始化状态
                self._sync_provider_ui(provider_id)

    def _on_key_change(self, provider_id: str) -> None:
        """API Key 变更时更新配置"""
        key = self._key_inputs[provider_id].value or ""
        setattr(self.config.api_keys, f"{provider_id}_key", key)
        self._key_status[provider_id].text = "已修改"
        self._key_status[provider_id].classes("text-orange", remove="text-positive text-grey-5")
        self._save_config()
        self._sync_provider_ui(provider_id)

    def _on_model_select_change(self, provider_id: str) -> None:
        """默认模型下拉变更: 保存到 config.model"""
        value = self._model_selects[provider_id].value or ""
        if provider_id == "glm":
            self.config.model.search_model = value
        elif provider_id == "deepseek":
            self.config.model.evaluate_model = value
        elif provider_id == "qwen":
            self.config.model.write_model = value
        self._save_config()

    def _sync_provider_ui(self, provider_id: str) -> None:
        """根据当前配置刷新某提供商的 UI 状态"""
        key = self._key_inputs[provider_id].value or ""
        enabled = self.config.enabled_models.get(provider_id, [])
        refreshed_at = self.config.model_refreshed_at.get(provider_id, "")

        model_select = self._model_selects[provider_id]
        container = self._model_checklist_container[provider_id]
        hint = self._model_hint[provider_id]
        timestamp_label = self._model_timestamp[provider_id]
        model_status = self._model_status[provider_id]

        if not key:
            hint.set_text("")
            model_status.set_text("")
            model_select.options = []
            model_select.value = ""
            model_select.disable()
            container.set_visibility(False)
            return

        prev = self._prev_keys.get(provider_id, "")
        if prev and prev != key:
            hint.set_text("⚠ API Key 已变更，请重新测试连接")
            hint.classes("text-orange-6")
            model_status.set_text("")
            model_select.options = []
            model_select.value = ""
            model_select.disable()
            container.set_visibility(False)
            self._clear_checkboxes(provider_id)
            self.config.enabled_models[provider_id] = []
            self.config.model_refreshed_at[provider_id] = ""
            self._save_config()
            return

        if not enabled:
            hint.set_text("⚠ 请先测试连接以获取可用模型")
            hint.classes("text-orange-6")
            model_status.set_text("")
            model_select.options = []
            model_select.value = ""
            model_select.disable()
            container.set_visibility(False)
            return

        hint.set_text("")
        model_status.set_text(f"🔄 已拉取 {len(enabled)} 个模型")
        model_status.classes("text-caption text-positive")

        model_select.options = enabled
        current_val = model_select.value
        if current_val not in enabled:
            model_select.value = enabled[0]
        model_select.enable()

        self._populate_checkboxes(provider_id, enabled)

        if refreshed_at:
            timestamp_label.set_text(f"上次更新: {refreshed_at}")
        else:
            timestamp_label.set_text("")

        container.set_visibility(True)

    def _populate_checkboxes(self, provider_id: str, enabled: list[str]) -> None:
        """根据已启用列表填充 checkbox"""
        self._clear_checkboxes(provider_id)
        column = self._model_checklist_column[provider_id]

        with column:
            for model_id in enabled:
                cb = ui.checkbox(text=model_id, value=True, on_change=lambda e, pid=provider_id, mid=model_id: self._on_checkbox_change(pid, mid, e.value))
                self._model_checkboxes[provider_id].append(cb)

    def _clear_checkboxes(self, provider_id: str) -> None:
        """清除某提供商的 checkbox"""
        for cb in self._model_checkboxes.get(provider_id, []):
            cb.delete()
        self._model_checkboxes[provider_id] = []

    def _on_checkbox_change(self, provider_id: str, model_id: str, checked: bool) -> None:
        """checkbox 勾选变更: 更新 enabled_models 并保存"""
        enabled = self.config.enabled_models.get(provider_id, [])
        if checked and model_id not in enabled:
            enabled.append(model_id)
        elif not checked and model_id in enabled:
            enabled.remove(model_id)
        self.config.enabled_models[provider_id] = enabled
        self._sync_model_select(provider_id)
        self._save_config()

    def _select_all(self, provider_id: str) -> None:
        """全选"""
        for cb in self._model_checkboxes.get(provider_id, []):
            cb.value = True
        self.config.enabled_models[provider_id] = list(self.config.enabled_models.get(provider_id, []))
        self._sync_model_select(provider_id)
        self._save_config()

    def _deselect_all(self, provider_id: str) -> None:
        """取消全选"""
        for cb in self._model_checkboxes.get(provider_id, []):
            cb.value = False
        self.config.enabled_models[provider_id] = []
        self._sync_model_select(provider_id)
        self._save_config()

    def _sync_model_select(self, provider_id: str) -> None:
        """同步默认模型下拉到当前 enabled_models"""
        enabled = self.config.enabled_models.get(provider_id, [])
        model_select = self._model_selects[provider_id]
        model_select.options = enabled
        if model_select.value not in enabled:
            model_select.value = enabled[0] if enabled else ""

    def _test_connection(self, provider_id: str) -> None:
        """测试连接并拉取可用模型列表"""
        key = self._key_inputs[provider_id].value or ""
        status = self._key_status[provider_id]
        model_status = self._model_status[provider_id]
        hint = self._model_hint[provider_id]

        if not key:
            status.text = "✗ Key 为空"
            status.classes("text-negative", remove="text-positive text-orange text-grey-5")
            return

        status.text = "测试中..."
        model_status.set_text("连接测试中...")
        model_status.classes("text-caption text-orange-6")

        try:
            provider = create_provider(provider_id, api_key=key)
            provider.client.models.list()

            status.text = "✓ 已连接"
            status.classes("text-positive", remove="text-negative text-orange text-grey-5")

            try:
                models = provider.list_models()
                self.config.enabled_models[provider_id] = models
                from datetime import datetime
                self.config.model_refreshed_at[provider_id] = datetime.now().strftime("%Y-%m-%d %H:%M")
                self._prev_keys[provider_id] = key
            except Exception as e:
                model_status.set_text("✗ 模型列表拉取失败")
                model_status.classes("text-caption text-negative")
                ui.notify(f"模型列表拉取失败: {e}", type="negative")
                self._save_config()
                self._sync_provider_ui(provider_id)
                return

            self._save_config()
            self._sync_provider_ui(provider_id)
            ui.notify(f"{provider_id} 连接成功，已拉取 {len(models)} 个模型", type="positive")

        except Exception as e:
            status.text = "✗ 连接失败"
            status.classes("text-negative", remove="text-positive text-orange text-grey-5")
            model_status.set_text("")
            hint.set_text("")
            ui.notify(f"连接失败: {e}", type="negative")

    # ── 外部网站凭据 ─────────────────────────────────────────────

    def _build_credentials_section(self) -> None:
        with ui.card().classes("w-full q-mb-md"):
            ui.label("🌐 外部网站凭据").classes("text-subtitle1 q-mb-md text-primary")

            # BOSS 直聘
            with ui.row().classes("w-full items-center gap-4"):
                ui.label("BOSS 直聘").classes("w-24 text-body2 text-grey-7")
                self._boss_status = ui.label("").classes("text-caption")
                ui.button("打开浏览器登录", on_click=self._boss_login).props("flat dense color=primary")
                self._update_boss_status()

            # LinkedIn (V2 预留)
            with ui.row().classes("w-full items-center gap-4").style("opacity:0.5"):
                ui.label("LinkedIn").classes("w-24 text-body2 text-grey-5")
                ui.label("即将支持").classes("text-caption text-grey-5")
                ui.button("未开通").props("flat dense disabled")

    def _update_boss_status(self) -> None:
        """更新 BOSS 直聘 Cookie 状态"""
        from pathlib import Path
        from cassiel.collector.boss import COOKIES_FILE

        if COOKIES_FILE.exists():
            self._boss_status.text = "✓ 已登录"
            self._boss_status.classes("text-positive", remove="text-orange text-grey-5 text-negative")
            self.config.credentials.boss_zhipin.status = "active"
        else:
            self._boss_status.text = "⚠ 未登录"
            self._boss_status.classes("text-orange", remove="text-positive text-grey-5 text-negative")
            self.config.credentials.boss_zhipin.status = "unset"

    def _boss_login(self) -> None:
        """打开浏览器让用户手动登录 BOSS 直聘"""
        try:
            from cassiel.collector.boss import BossCollector

            async def _do_login() -> None:
                collector = BossCollector(headless=False)
                try:
                    page = collector._ensure_browser()
                    page.goto("https://www.zhipin.com/web/user/?ka=header-login")
                    ui.notify("请在浏览器中完成登录，登录成功后点击此按钮", type="info", timeout=10000)
                except Exception as e:
                    ui.notify(f"浏览器启动失败: {e}", type="negative")

            asyncio.ensure_future(_do_login())

        except ImportError:
            ui.notify("Playwright 未安装，无法启动浏览器", type="negative")

    # ── 搜索默认值 ─────────────────────────────────────────────

    def _build_search_defaults_section(self) -> None:
        with ui.card().classes("w-full"):
            ui.label("🔍 搜索默认值").classes("text-subtitle1 q-mb-md text-primary")

            search = self.config.search

            with ui.row().classes("w-full gap-4"):
                self._default_city = ui.select(
                    label="城市",
                    options=_CITY_NAMES,
                    value=search.city if search.city in _CITY_NAMES else _CITY_NAMES[0],
                    on_change=self._on_search_default_change,
                ).classes("flex-1").props("outlined dense")

                self._default_experience = ui.select(
                    label="经验要求",
                    options=_EXPERIENCE_OPTIONS,
                    value=search.experience if search.experience in _EXPERIENCE_OPTIONS else _EXPERIENCE_OPTIONS[0],
                    on_change=self._on_search_default_change,
                ).classes("flex-1").props("outlined dense")

            with ui.row().classes("w-full gap-4 q-mt-sm"):
                self._default_salary_min = ui.number(
                    label="最低薪资(K)",
                    value=search.salary_min or 15,
                    min=0, max=200, precision=0,
                    on_change=self._on_search_default_change,
                ).classes("flex-1").props("outlined dense")

                self._default_salary_max = ui.number(
                    label="最高薪资(K)",
                    value=search.salary_max or 50,
                    min=0, max=200, precision=0,
                    on_change=self._on_search_default_change,
                ).classes("flex-1").props("outlined dense")

            with ui.row().classes("w-full gap-4 q-mt-sm"):
                self._default_education = ui.select(
                    label="学历要求",
                    options=_EDUCATION_OPTIONS,
                    value=search.education if search.education in _EDUCATION_OPTIONS else _EDUCATION_OPTIONS[0],
                    on_change=self._on_search_default_change,
                ).classes("flex-1").props("outlined dense")

                self._default_max_pages = ui.number(
                    label="最大抓取页数",
                    value=search.max_pages,
                    min=1, max=10, precision=0,
                    on_change=self._on_search_default_change,
                ).classes("flex-1").props("outlined dense")

    def _on_search_default_change(self) -> None:
        """搜索默认值变更时更新配置"""
        city = self._default_city.value or _CITY_NAMES[0]
        default_cfg = SearchConfig()
        self.config.search = SearchConfig(
            keyword=self.config.search.keyword,
            city=city,
            city_code=default_cfg.CITY_CODES.get(city, default_cfg.city_code),
            salary_min=int(self._default_salary_min.value or 0),
            salary_max=int(self._default_salary_max.value or 0),
            experience=self._default_experience.value or "不限",
            education=self._default_education.value or "不限",
            max_pages=int(self._default_max_pages.value or 3),
        )
        self._save_config()
        ui.notify("搜索默认值已保存", type="info")

    def _save_config(self) -> None:
        """保存配置到 config.json"""
        try:
            self.config.to_json()
        except Exception as e:
            ui.notify(f"配置保存失败: {e}", type="negative")
