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
        """提供商有 Key 但 enabled_models 为空"""
        config = AppConfig()
        config.api_keys.deepseek_key = "sk-test"

        labels = get_available_model_labels(config)
        assert labels == []
