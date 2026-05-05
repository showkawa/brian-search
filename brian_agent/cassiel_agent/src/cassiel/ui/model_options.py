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
