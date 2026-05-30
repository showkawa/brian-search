"""LLM 提供商单元测试"""
import pytest
from unittest.mock import MagicMock

from cassiel.llm.providers import LLMProvider, ProviderConfig


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
