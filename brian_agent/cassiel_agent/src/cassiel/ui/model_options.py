"""共享模型选项 — 模型定义与查询工具

招聘页和设置页共同使用此模块。
"""

from __future__ import annotations

from cassiel.config.settings import AppConfig

# ═══════════════════════════════════════════════════════════════
# 模型选项 — 格式: "provider:model" → 显示标签
# ═══════════════════════════════════════════════════════════════

_MODEL_OPTIONS: dict[str, str] = {
    "glm:glm-4-flash": "GLM-4 Flash (智谱) — 快速",
    "glm:glm-4-plus": "GLM-4 Plus (智谱) — 均衡",
    "glm:glm-4": "GLM-4 (智谱) — 标准",
    "qwen:qwen-turbo": "Qwen Turbo (通义) — 快速",
    "qwen:qwen-plus": "Qwen Plus (通义) — 均衡",
    "qwen:qwen-max": "Qwen Max (通义) — 高质量",
    "deepseek:deepseek-chat": "DeepSeek Chat — 通用",
    "deepseek:deepseek-coder": "DeepSeek Coder — 代码",
}

_PROVIDER_NAMES: dict[str, str] = {
    "glm": "智谱 GLM",
    "qwen": "通义 Qwen",
    "deepseek": "DeepSeek",
}


def parse_model_key(model_key: str) -> tuple[str, str]:
    """解析 'provider:model' → ('provider', 'model')"""
    try:
        provider, model = model_key.split(":", 1)
        return provider.strip(), model.strip()
    except ValueError:
        return "glm", "glm-4-flash"


def all_model_labels() -> list[str]:
    """所有模型标签"""
    return list(_MODEL_OPTIONS.values())


def key_from_label(label: str, default: str = "deepseek:deepseek-chat") -> str:
    """从显示标签反查 model key"""
    return next((k for k, v in _MODEL_OPTIONS.items() if v == label), default)


def get_models_for_provider(provider: str, include_label: bool = True) -> list[str]:
    """获取某提供商的可用模型列表

    Args:
        provider: 提供商名称 (glm / qwen / deepseek)
        include_label: 是否返回显示标签（True）还是 model key（False）

    Returns:
        模型标签列表，如 ["GLM-4 Flash (智谱) — 快速", ...]
    """
    if include_label:
        return [v for k, v in _MODEL_OPTIONS.items() if k.startswith(f"{provider}:")]
    return [k for k in _MODEL_OPTIONS if k.startswith(f"{provider}:")]


def get_available_providers(config: AppConfig) -> list[str]:
    """获取已配置 Key 的提供商列表（名称排序）"""
    api = config.api_keys
    providers = []
    for pid, name in _PROVIDER_NAMES.items():
        key = getattr(api, f"{pid}_key", "")
        if key:
            providers.append(pid)
    return sorted(providers)


def get_available_model_labels(config: AppConfig) -> list[str]:
    """获取所有已配置 Key 的提供商的模型标签（用于招聘页下拉选项）"""
    available = get_available_providers(config)
    if not available:
        return all_model_labels()  # 回退：显示全部，用户需要看到选项
    labels = []
    for pid in available:
        labels.extend(get_models_for_provider(pid, include_label=True))
    return labels


def get_default_model_for_provider(config: AppConfig, provider: str) -> str:
    """从 config 读取某提供商的默认模型标签"""
    model_name = getattr(config.model, f"write_model" if provider == "qwen" else f"search_model", "glm-4-flash")
    # 查找匹配的标签
    for key, label in _MODEL_OPTIONS.items():
        p, m = parse_model_key(key)
        if p == provider:
            return label
    return get_models_for_provider(provider)[0] if get_models_for_provider(provider) else ""


def get_missing_providers(config: AppConfig) -> list[str]:
    """获取未配置 Key 的提供商名称列表"""
    available = get_available_providers(config)
    return [name for pid, name in _PROVIDER_NAMES.items() if pid not in available]
