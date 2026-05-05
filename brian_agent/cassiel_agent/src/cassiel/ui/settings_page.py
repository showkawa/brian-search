"""账户配置页面 — API Key + 外部凭据 + 搜索默认值"""

from __future__ import annotations

import asyncio

from nicegui import ui

from cassiel.config.settings import AppConfig, SearchConfig, CredentialEntry
from cassiel.llm.providers import create_provider
from cassiel.ui.model_options import (
    _MODEL_OPTIONS, get_models_for_provider, parse_model_key, key_from_label,
)

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

                # 模型选择器 (在 key/status 行之后新增)
                model_options = get_models_for_provider(provider_id, include_label=True)
                current_model = getattr(self.config.model, f"{provider_id}_model", "")
                current_label = model_options[0] if model_options else "无"
                for key, lbl in _MODEL_OPTIONS.items():
                    p, m = parse_model_key(key)
                    if p == provider_id and m == current_model:
                        current_label = lbl
                        break
                with ui.row().classes("w-full items-center gap-4 q-mb-sm"):
                    ui.label("").classes("w-24")  # 占位，对齐
                    model_select = ui.select(
                        label="默认模型",
                        options=model_options,
                        value=current_label,
                        on_change=lambda e, pid=provider_id: self._on_model_change(pid),
                    ).classes("w-56").props("outlined dense")
                    self._model_selects[provider_id] = model_select
                    if not (self.config.api_keys.glm_key if provider_id == "glm" else
                            self.config.api_keys.qwen_key if provider_id == "qwen" else
                            self.config.api_keys.deepseek_key):
                        model_select.disable()

    def _on_key_change(self, provider_id: str) -> None:
        """API Key 变更时更新配置"""
        key = self._key_inputs[provider_id].value or ""
        setattr(self.config.api_keys, f"{provider_id}_key", key)
        self._key_status[provider_id].text = "已修改"
        self._key_status[provider_id].classes("text-orange", remove="text-positive text-grey-5")
        self._save_config()
        # 根据 Key 是否为空启用/禁用模型选择器
        if provider_id in self._model_selects:
            has_key = bool(self._key_inputs[provider_id].value or "")
            self._model_selects[provider_id].set_enabled(has_key)

    def _on_model_change(self, provider_id: str) -> None:
        """模型选择变更 → 保存到 config"""
        label = self._model_selects[provider_id].value
        model_key = key_from_label(label)
        p, m = parse_model_key(model_key)
        setattr(self.config.model, f"{provider_id}_model", m)
        self._save_config()

    def _test_connection(self, provider_id: str) -> None:
        """测试 LLM 连接 — 通过 /v1/models 接口验证 token，不消耗任何额度

        三个提供商 (DeepSeek / GLM / Qwen) 均支持 OpenAI 兼容的 models.list() 接口。
        此请求仅验证 API Key 有效性，不产生 token 消耗。
        """
        key = self._key_inputs[provider_id].value or ""
        status = self._key_status[provider_id]

        if not key:
            status.text = "✗ Key 为空"
            status.classes("text-negative", remove="text-positive text-orange text-grey-5")
            return

        status.text = "测试中..."
        try:
            provider = create_provider(provider_id, api_key=key)
            # 零消耗验证: 调用 /v1/models 接口，仅校验鉴权
            provider.client.models.list()
            status.text = "✓ 已连接"
            status.classes("text-positive", remove="text-negative text-orange text-grey-5")
            if provider_id in self._model_selects:
                self._model_selects[provider_id].enable()
            ui.notify(f"{provider_id} 连接成功", type="positive")
        except Exception as e:
            status.text = "✗ 连接失败"
            status.classes("text-negative", remove="text-positive text-orange text-grey-5")
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
