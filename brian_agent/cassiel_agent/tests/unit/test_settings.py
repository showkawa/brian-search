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
