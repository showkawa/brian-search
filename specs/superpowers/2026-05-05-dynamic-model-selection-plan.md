# 动态模型选择 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 模型列表从提供商 API 动态获取，用户通过 checklist 勾选启用，招聘页下拉只显示已启用模型，模型名使用原始 ID。

**Architecture:** 在 `LLMProvider` 基类加 `list_models()` → `AppConfig` 加 `enabled_models` + `model_refreshed_at` 持久化 → `model_options.py` 改为动态读取 config → `settings_page.py` 加 checklist UI → `recruit_page.py` 约束下拉。

**Tech Stack:** Python 3.11+, NiceGUI, OpenAI SDK, dataclasses

---

### Task 1: `LLMProvider.list_models()` — 从 API 获取模型列表

**Files:**
- Modify: `brian_agent/cassiel_agent/src/cassiel/llm/providers.py`
- Create: `brian_agent/cassiel_agent/tests/unit/test_providers.py`

- [ ] **Step 1: 创建测试文件**

```python
"""LLM 提供商单元测试"""
import pytest
from unittest.mock import MagicMock, patch

from cassiel.llm.providers import LLMProvider, ProviderConfig, create_provider, PROVIDER_REGISTRY


class MockProvider(LLMProvider):
    """测试用具体实现"""
    def get_provider_name(self) -> str:
        return "Mock"


class TestListModels:
    """list_models() 测试"""

    def test_returns_model_ids_from_api(self):
        """从 API 返回模型 ID 列表"""
        mock_client = MagicMock()
        mock_client.models.list.return_value.data = [
            MagicMock(id="model-a"),
            MagicMock(id="model-b"),
        ]
        config = ProviderConfig(api_key="sk-test", base_url="http://test")
        provider = MockProvider(config)
        provider._client = mock_client

        result = provider.list_models()

        assert result == ["model-a", "model-b"]
        mock_client.models.list.assert_called_once()

    def test_empty_list_when_no_models(self):
        """API 无模型时返回空列表"""
        mock_client = MagicMock()
        mock_client.models.list.return_value.data = []
        config = ProviderConfig(api_key="sk-test", base_url="http://test")
        provider = MockProvider(config)
        provider._client = mock_client

        result = provider.list_models()

        assert result == []

    def test_propagates_api_error(self):
        """API 错误时向上抛出"""
        mock_client = MagicMock()
        mock_client.models.list.side_effect = RuntimeError("API down")
        config = ProviderConfig(api_key="sk-test", base_url="http://test")
        provider = MockProvider(config)
        provider._client = mock_client

        with pytest.raises(RuntimeError, match="API down"):
            provider.list_models()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest brian_agent/cassiel_agent/tests/unit/test_providers.py -v
```

预期: `AttributeError: 'MockProvider' object has no attribute 'list_models'`

- [ ] **Step 3: 在 `LLMProvider` 基类添加 `list_models()` 方法**

在 `providers.py` 的 `LLMProvider` 类中，`chat_json()` 方法之后添加:

```python
    def list_models(self) -> list[str]:
        """获取提供商可用模型列表

        Returns:
            模型 ID 列表，如 ["deepseek-chat", "deepseek-coder"]
        """
        resp = self.client.models.list()
        return [m.id for m in resp.data]
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest brian_agent/cassiel_agent/tests/unit/test_providers.py::TestListModels -v
```

预期: 3 passed

- [ ] **Step 5: 提交**

```bash
git add brian_agent/cassiel_agent/src/cassiel/llm/providers.py brian_agent/cassiel_agent/tests/unit/test_providers.py
git commit -m "feat: add list_models() to LLMProvider base class"
```

---

### Task 2: `AppConfig` 新增 `enabled_models` + `model_refreshed_at` 字段

**Files:**
- Modify: `brian_agent/cassiel_agent/src/cassiel/config/settings.py`
- Modify: `brian_agent/cassiel_agent/tests/unit/test_providers.py` → 改用独立文件

- [ ] **Step 1: 创建测试文件**

```python
"""配置管理单元测试"""
import json
import tempfile
from pathlib import Path

from cassiel.config.settings import AppConfig


class TestEnabledModels:
    """enabled_models 和 model_refreshed_at 字段测试"""

    def test_default_empty(self):
        """默认值为空"""
        config = AppConfig()
        assert config.enabled_models == {}
        assert config.model_refreshed_at == {}

    def test_serialize_enabled_models(self):
        """enabled_models 序列化到 JSON"""
        config = AppConfig()
        config.enabled_models = {
            "deepseek": ["deepseek-chat", "deepseek-coder"],
            "glm": ["glm-4-flash"],
        }
        config.model_refreshed_at = {
            "deepseek": "2026-05-05T14:30:00",
            "glm": "2026-05-05T14:31:00",
        }

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as f:
            config.to_json(f.name)
            tmp_path = Path(f.name)

        raw = json.loads(tmp_path.read_text(encoding="utf-8"))
        assert raw["enabled_models"]["deepseek"] == ["deepseek-chat", "deepseek-coder"]
        assert raw["enabled_models"]["glm"] == ["glm-4-flash"]
        assert raw["model_refreshed_at"]["deepseek"] == "2026-05-05T14:30:00"
        tmp_path.unlink()

    def test_deserialize_enabled_models(self):
        """enabled_models 从 JSON 反序列化"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as f:
            json.dump({
                "search": {},
                "model": {},
                "api_keys": {},
                "credentials": {"boss_zhipin": {}, "linkedin": {}},
                "enabled_models": {"qwen": ["qwen-plus"]},
                "model_refreshed_at": {"qwen": "2026-05-05T12:00:00"},
            }, f)
            tmp_path = Path(f.name)

        config = AppConfig.from_json(tmp_path)
        assert config.enabled_models == {"qwen": ["qwen-plus"]}
        assert config.model_refreshed_at == {"qwen": "2026-05-05T12:00:00"}
        tmp_path.unlink()

    def test_deserialize_without_new_fields(self):
        """旧配置文件没有新字段时不报错"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as f:
            json.dump({
                "search": {},
                "model": {},
                "api_keys": {},
                "credentials": {"boss_zhipin": {}, "linkedin": {}},
            }, f)
            tmp_path = Path(f.name)

        config = AppConfig.from_json(tmp_path)
        assert config.enabled_models == {}
        assert config.model_refreshed_at == {}
        tmp_path.unlink()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest brian_agent/cassiel_agent/tests/unit/test_settings.py -v
```

预期: `TypeError: AppConfig.__init__() got an unexpected keyword argument 'enabled_models'`

- [ ] **Step 3: 在 `AppConfig` 添加字段**

修改 `settings.py`:

(1) 导入 `field`（已有），无需新增导入。

(2) 在 `AppConfig` 类的 `credentials` 字段之后添加:

```python
    enabled_models: dict[str, list[str]] = field(default_factory=dict)
    model_refreshed_at: dict[str, str] = field(default_factory=dict)
```

(3) 修改 `to_json()` 方法，在 `data` 字典中追加:

```python
            "enabled_models": self.enabled_models,
            "model_refreshed_at": self.model_refreshed_at,
```

(4) 修改 `from_json()` 方法，在返回 `cls(...)` 之前，解析新字段:

```python
        enabled_models = raw.get("enabled_models", {})
        model_refreshed_at = raw.get("model_refreshed_at", {})

        return cls(
            search=SearchConfig(...),
            model=ModelConfig(...),
            api_keys=APIKeys(...),
            credentials=CredentialsConfig.from_dict(credentials_data),
            enabled_models=enabled_models,
            model_refreshed_at=model_refreshed_at,
        )
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest brian_agent/cassiel_agent/tests/unit/test_settings.py::TestEnabledModels -v
```

预期: 4 passed

- [ ] **Step 5: 提交**

```bash
git add brian_agent/cassiel_agent/src/cassiel/config/settings.py brian_agent/cassiel_agent/tests/unit/test_settings.py
git commit -m "feat: add enabled_models and model_refreshed_at to AppConfig"
```

---

### Task 3: 重构 `model_options.py` — 删除硬编码，改为动态读取

**Files:**
- Modify: `brian_agent/cassiel_agent/src/cassiel/ui/model_options.py`
- Create: `brian_agent/cassiel_agent/tests/unit/test_model_options.py`

- [ ] **Step 1: 创建测试文件**

```python
"""模型选项单元测试"""
from cassiel.config.settings import AppConfig
from cassiel.ui.model_options import (
    get_models_for_provider,
    get_available_model_labels,
)


class TestGetModelsForProvider:
    """从 enabled_models 获取模型列表"""

    def test_returns_enabled_models(self):
        config = AppConfig()
        config.enabled_models = {"deepseek": ["deepseek-chat", "deepseek-coder"]}

        result = get_models_for_provider(config, "deepseek")
        assert result == ["deepseek-chat", "deepseek-coder"]

    def test_returns_empty_when_not_enabled(self):
        config = AppConfig()
        config.enabled_models = {"deepseek": ["deepseek-chat"]}

        result = get_models_for_provider(config, "qwen")
        assert result == []

    def test_returns_empty_when_no_config(self):
        config = AppConfig()
        result = get_models_for_provider(config, "glm")
        assert result == []


class TestGetAvailableModelLabels:
    """从已启用模型获取招聘页下拉选项"""

    def test_only_returns_enabled_models(self):
        config = AppConfig()
        config.api_keys.deepseek_key = "sk-test"
        config.api_keys.glm_key = "sk-test"
        config.enabled_models = {
            "deepseek": ["deepseek-chat"],
            "glm": ["glm-4-flash", "glm-4-plus"],
        }

        labels = get_available_model_labels(config)
        # label 即原始 model ID
        assert "deepseek-chat" in labels
        assert "glm-4-flash" in labels
        assert "glm-4-plus" in labels
        assert "deepseek-coder" not in labels

    def test_returns_empty_when_no_provider_has_key(self):
        config = AppConfig()
        config.enabled_models = {"deepseek": ["deepseek-chat"]}

        labels = get_available_model_labels(config)
        assert labels == []

    def test_fallback_when_provider_has_key_but_no_enabled(self):
        """提供商有 Key 但 enabled_models 为空: 提示用户去测试连接"""
        config = AppConfig()
        config.api_keys.deepseek_key = "sk-test"

        labels = get_available_model_labels(config)
        assert labels == []
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest brian_agent/cassiel_agent/tests/unit/test_model_options.py -v
```

预期: 测试失败（当前使用硬编码 `_MODEL_OPTIONS`）

- [ ] **Step 3: 重构 `model_options.py`**

删除硬编码 `_MODEL_OPTIONS`，全部改为从 `config.enabled_models` 读取:

```python
"""共享模型选项 — 模型定义与查询工具

招聘页和设置页共同使用此模块。
"""

from __future__ import annotations

from cassiel.config.settings import AppConfig

_PROVIDER_NAMES: dict[str, str] = {
    "glm": "智谱 GLM",
    "qwen": "通义 Qwen",
    "deepseek": "DeepSeek",
}


def parse_model_key(model_key: str) -> tuple[str, str]:
    """解析 'provider:model' -> ('provider', 'model')"""
    try:
        provider, model = model_key.split(":", 1)
        return provider.strip(), model.strip()
    except ValueError:
        return "glm", "glm-4-flash"


def get_models_for_provider(config: AppConfig, provider: str) -> list[str]:
    """获取某提供商已启用的模型列表（原始模型 ID）"""
    return config.enabled_models.get(provider, [])


def get_available_providers(config: AppConfig) -> list[str]:
    """获取已配置 Key 的提供商列表"""
    api = config.api_keys
    providers = []
    for pid, name in _PROVIDER_NAMES.items():
        key = getattr(api, f"{pid}_key", "")
        if key:
            providers.append(pid)
    return sorted(providers)


def get_available_model_labels(config: AppConfig) -> list[str]:
    """获取已启用 + 已配置 Key 的模型列表（用于招聘页下拉）"""
    available = get_available_providers(config)
    labels = []
    for pid in available:
        labels.extend(get_models_for_provider(config, pid))
    return labels


def get_missing_providers(config: AppConfig) -> list[str]:
    """获取未配置 Key 的提供商名称列表"""
    available = get_available_providers(config)
    return [name for pid, name in _PROVIDER_NAMES.items() if pid not in available]


def provider_name(provider_id: str) -> str:
    """获取提供商中文名"""
    return _PROVIDER_NAMES.get(provider_id, provider_id)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest brian_agent/cassiel_agent/tests/unit/test_model_options.py -v
```

预期: 全部通过

- [ ] **Step 5: 提交**

```bash
git add brian_agent/cassiel_agent/src/cassiel/ui/model_options.py brian_agent/cassiel_agent/tests/unit/test_model_options.py
git commit -m "refactor: model_options reads dynamically from enabled_models config"
```

---

### Task 4: 重构 `settings_page.py` — 核心 UI 改造

**Files:**
- Modify: `brian_agent/cassiel_agent/src/cassiel/ui/settings_page.py`

> 设置页改造是最复杂的部分。由于 NiceGUI 是声明式且测试 UI 困难，本任务不写 UI 测试，改为手动验证清单。

- [ ] **Step 1: 备份当前 settings_page.py（可选，方便回滚）**

```bash
cp brian_agent/cassiel_agent/src/cassiel/ui/settings_page.py brian_agent/cassiel_agent/src/cassiel/ui/settings_page.py.bak
```

- [ ] **Step 2: 重写 `_build_api_keys_section` — 添加 checklist、状态标签、时间戳**

完整替换 `settings_page.py` 中的 `_build_api_keys_section` 及相关方法:

```python
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
            self._model_status: dict[str, ui.label] = {}       # 拉取状态
            self._model_checkboxes: dict[str, list[ui.checkbox]] = {}
            self._model_checklist_container: dict[str, ui.element] = {}
            self._model_checklist_column: dict[str, ui.column] = {}
            self._model_selects: dict[str, ui.select] = {}
            self._model_timestamp: dict[str, ui.label] = {}     # 更新时间
            self._model_hint: dict[str, ui.label] = {}          # 提示文字
            self._prev_keys: dict[str, str] = {}

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

                # 第三行: 提示文字 (Key 未测试等) + 默认模型下拉
                with ui.row().classes("w-full items-center gap-4 q-mb-xs"):
                    ui.label("").classes("w-24")
                    hint_label = ui.label("").classes("text-caption")
                    self._model_hint[provider_id] = hint_label

                with ui.row().classes("w-full items-center gap-4 q-mb-sm"):
                    ui.label("").classes("w-24")
                    enabled_models = self.config.enabled_models.get(provider_id, [])
                    model_options = enabled_models if enabled_models else []
                    current_model_name = getattr(self.config.model, f"search_model" if provider_id == "glm" else
                                                  "evaluate_model" if provider_id == "deepseek" else "write_model", "")
                    current_value = current_model_name if current_model_name in model_options else (model_options[0] if model_options else "")
                    model_select = ui.select(
                        label="默认模型",
                        options=[],
                        value=current_value,
                        on_change=lambda e, pid=provider_id: self._on_model_select_change(pid),
                    ).classes("w-56").props("outlined dense")
                    self._model_selects[provider_id] = model_select

                # 第四行: checklist 容器（默认隐藏）
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
            # Key 为空: 清空
            hint.set_text("")
            model_status.set_text("")
            model_select.options = []
            model_select.value = ""
            model_select.disable()
            container.set_visibility(False)
            return

        # 比较 Key 是否变更
        prev = self._prev_keys.get(provider_id, "")
        if prev and prev != key:
            # Key 变更了
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
            # 已填 Key 但未测试
            hint.set_text("⚠ 请先测试连接以获取可用模型")
            hint.classes("text-orange-6")
            model_status.set_text("")
            model_select.options = []
            model_select.value = ""
            model_select.disable()
            container.set_visibility(False)
            return

        # 已有 enabled_models
        hint.set_text("")
        model_status.set_text(f"🔄 已拉取 {len(enabled)} 个模型")
        model_status.classes("text-caption text-positive")

        # 更新下拉
        model_select.options = enabled
        current_val = model_select.value
        if current_val not in enabled:
            model_select.value = enabled[0]
        model_select.enable()

        # 更新 checklist
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

    def _on_model_select_change(self, provider_id: str) -> None:
        """默认模型下拉变更: 保存到 config.model"""
        value = self._model_selects[provider_id].value or ""
        # 更新对应阶段的默认模型
        if provider_id == "glm":
            self.config.model.search_model = value
        elif provider_id == "deepseek":
            self.config.model.evaluate_model = value
        elif provider_id == "qwen":
            self.config.model.write_model = value
        self._save_config()
```

- [ ] **Step 3: 重写 `_on_key_change` — 加入 Key 变更检测**

替换 `_on_key_change` 方法:

```python
    def _on_key_change(self, provider_id: str) -> None:
        """API Key 变更时更新配置"""
        key = self._key_inputs[provider_id].value or ""
        setattr(self.config.api_keys, f"{provider_id}_key", key)
        self._key_status[provider_id].text = "已修改"
        self._key_status[provider_id].classes("text-orange", remove="text-positive text-grey-5")
        self._save_config()
        self._sync_provider_ui(provider_id)
```

- [ ] **Step 4: 重写 `_test_connection` — 成功后拉取模型并全选**

替换 `_test_connection` 方法:

```python
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
            # 验证连接
            provider.client.models.list()

            status.text = "✓ 已连接"
            status.classes("text-positive", remove="text-negative text-orange text-grey-5")

            # 拉取模型列表
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

    def _on_model_change(self, provider_id: str) -> None:
        """(已废弃，由 _on_model_select_change 替代)"""
        pass
```

- [ ] **Step 5: 删除旧的不再需要的引用**

在文件顶部，删除 `from cassiel.ui.model_options import` 中不再需要的导入:

```python
from cassiel.ui.model_options import (
    get_models_for_provider, parse_model_key, provider_name,
)
```

> `_MODEL_OPTIONS`, `key_from_label` 不再使用。

- [ ] **Step 6: 手动验证清单**

启动应用并逐项验证:

```bash
python brian_agent/cassiel_agent/run.py
```

| # | 验证项 | 预期 |
|---|--------|------|
| 1 | Key 为空 → 无 checklist | ✓ |
| 2 | 填 Key 不测试 → "请先测试连接" | ✓ |
| 3 | 点测试连接 → "连接测试中" → "已拉取 N 个模型" | ✓ |
| 4 | checklist 全选按钮 | ✓ |
| 5 | checklist 取消全选按钮 | ✓ |
| 6 | 取消勾选 → 下拉立即更新 | ✓ |
| 7 | 时间戳显示 | ✓ |
| 8 | 修改 Key → "Key 已变更，请重新测试" | ✓ |

- [ ] **Step 7: 提交**

```bash
git add brian_agent/cassiel_agent/src/cassiel/ui/settings_page.py
git commit -m "feat: dynamic model checklist in settings page"
```

---

### Task 5: 更新 `recruit_page.py` — 约束下拉 + 空模型引导

**Files:**
- Modify: `brian_agent/cassiel_agent/src/cassiel/ui/recruit_page.py`

- [ ] **Step 1: 更新 `recruit_page.py` 中的模型选择栏**

在 `recruit_page.py` 文件顶部，更新导入:

```python
from cassiel.ui.model_options import (
    get_available_model_labels, get_missing_providers,
)
```

> `_MODEL_OPTIONS` 不再需要导入。

替换模型选择栏代码 (约 line 182-219)：

完整的替换代码为:

```python
        # ── LLM 模型选择栏 ──
        with ui.row().classes("w-full q-mb-md gap-4 items-center"):
            ui.icon("settings").classes("text-grey-6")

            available_labels = get_available_model_labels(self.config)
            missing = get_missing_providers(self.config)

            if not available_labels:
                with ui.row().classes("items-center"):
                    ui.icon("warning").classes("text-orange q-mr-sm")
                    ui.label(
                        "暂无可用模型，请先在左侧「⚙️ 账户配置」中测试连接并启用模型"
                    ).classes("text-body1 text-orange-8")
            else:
                search_default = self.config.model.search_model or ""
                eval_default = self.config.model.evaluate_model or ""
                write_default = self.config.model.write_model or ""

                search_model_select = ui.select(
                    label="搜索/采集模型",
                    options=available_labels,
                    value=search_default if search_default in available_labels else (available_labels[0] if available_labels else ""),
                ).classes("w-64").props("outlined dense")

                eval_model_select = ui.select(
                    label="评估/筛选模型",
                    options=available_labels,
                    value=eval_default if eval_default in available_labels else (available_labels[0] if available_labels else ""),
                ).classes("w-64").props("outlined dense")

                write_model_select = ui.select(
                    label="文案生成模型",
                    options=available_labels,
                    value=write_default if write_default in available_labels else (available_labels[0] if available_labels else ""),
                ).classes("w-64").props("outlined dense")
```

- [ ] **Step 2: 修复旧代码中引用 `_MODEL_OPTIONS` 的地方**

`recruit_page.py` 中不再有对 `_MODEL_OPTIONS` 的引用（label 即 model ID）。

搜索确认没有残留引用:
```bash
rg "_MODEL_OPTIONS" brian_agent/cassiel_agent/src/cassiel/ui/recruit_page.py
```
预期: 无匹配。

- [ ] **Step 3: 运行现有测试确保未破坏**

```bash
python -m pytest brian_agent/cassiel_agent/tests/ -v
```

预期: 所有现有测试通过。

- [ ] **Step 4: 手动验证**

启动应用:
```bash
python brian_agent/cassiel_agent/run.py
```

| # | 验证项 | 预期 |
|---|--------|------|
| 1 | 无可用模型 → 显示引导文字 | ✓ |
| 2 | 有已启用模型 → 三个下拉框正常显示 | ✓ |
| 3 | 下拉选项 = enabled_models 中的模型 | ✓ |
| 4 | 模型名 = 原始 ID | ✓ |

- [ ] **Step 5: 提交**

```bash
git add brian_agent/cassiel_agent/src/cassiel/ui/recruit_page.py
git commit -m "feat: constrain recruit model dropdowns to enabled models"
```

---

### Task 6: 清理 + 最终验证

- [ ] **Step 1: 删除设置页备份文件**

```bash
rm -f brian_agent/cassiel_agent/src/cassiel/ui/settings_page.py.bak
```

- [ ] **Step 2: 检查所有文件无遗留垃圾引用**

```bash
rg "_MODEL_OPTIONS" brian_agent/cassiel_agent/src/
rg "key_from_label" brian_agent/cassiel_agent/src/
rg "from cassiel.ui.model_options import" brian_agent/cassiel_agent/src/cassiel/ui/settings_page.py
rg "from cassiel.ui.model_options import" brian_agent/cassiel_agent/src/cassiel/ui/recruit_page.py
```

预期: `_MODEL_OPTIONS`、`key_from_label` 不再被 src/ 下任何文件引用。

- [ ] **Step 3: 运行全量测试**

```bash
python -m pytest brian_agent/cassiel_agent/tests/ -v
```

预期: 全部通过。

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "chore: cleanup after dynamic model selection refactor"
```

---

### Task 7: 更新 `config.json` 示例

**Files:**
- Modify: `brian_agent/cassiel_agent/config.json`

- [ ] **Step 1: 在 config.json 中新增字段**

在现有 `config.json` 末尾追加:

```json
  "enabled_models": {
    "deepseek": ["deepseek-chat", "deepseek-coder"],
    "glm": [],
    "qwen": []
  },
  "model_refreshed_at": {
    "deepseek": "",
    "glm": "",
    "qwen": ""
  }
```

- [ ] **Step 2: 提交**

```bash
git add brian_agent/cassiel_agent/config.json
git commit -m "chore: add enabled_models and model_refreshed_at to config.json"
```
