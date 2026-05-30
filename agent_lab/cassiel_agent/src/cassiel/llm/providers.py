"""LLM统一适配层 — OpenAI兼容接口

支持三个国产大模型提供商:
- GLM (智谱AI): glm-4-flash / glm-4-plus
- Qwen (通义千问): qwen-plus / qwen-turbo
- DeepSeek: deepseek-chat / deepseek-coder

所有提供商均使用 OpenAI 兼容 API 格式，
通过 openai 库的 base_url 参数切换不同服务端点。
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)


# ── 提供商配置 ──────────────────────────────────────────────

@dataclass
class ProviderConfig:
    """LLM提供商配置

    Attributes:
        api_key: API密钥
        base_url: API基础URL
        model_name: 默认模型名称
        temperature: 生成温度
        max_tokens: 最大生成token数
    """

    api_key: str = ""
    base_url: str = ""
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048


# ── 抽象基类 ──────────────────────────────────────────────

class LLMProvider(ABC):
    """LLM提供商抽象基类

    所有提供商必须实现 chat 方法。
    使用 OpenAI 兼容接口，通过 base_url 区分不同服务。
    """

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        """懒加载 OpenAI 客户端"""
        if self._client is None:
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )
        return self._client

    @abstractmethod
    def get_provider_name(self) -> str:
        """返回提供商名称"""
        ...

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """发送聊天请求

        Args:
            messages: 消息列表 [{"role": "system/user/assistant", "content": "..."}]
            model: 模型名称 (默认使用配置中的模型)
            temperature: 生成温度
            max_tokens: 最大token数

        Returns:
            模型生成的文本内容
        """
        model = model or self.config.model_name
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        logger.info(
            "[%s] 请求模型: %s, 消息数: %d",
            self.get_provider_name(), model, len(messages),
        )

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            content = response.choices[0].message.content or ""
            logger.info("[%s] 响应长度: %d 字符", self.get_provider_name(), len(content))
            return content
        except Exception as e:
            logger.error("[%s] 请求失败: %s", self.get_provider_name(), e)
            raise

    def chat_json(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """发送聊天请求并解析JSON响应

        Returns:
            解析后的字典
        """
        raw = self.chat(messages=messages, model=model, **kwargs)
        # 尝试提取JSON块
        text = raw.strip()
        if text.startswith("```"):
            # 去除markdown代码块包裹
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        try:
            return json.loads(text)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            logger.warning("JSON解析失败，原始响应: %s", raw[:200])
            return {"raw_response": raw}

    def list_models(self) -> list[str]:
        """获取提供商可用模型列表

        Returns:
            模型 ID 列表，如 ["deepseek-chat", "deepseek-coder"]
        """
        resp = self.client.models.list()
        return [m.id for m in resp.data]


# ── 具体提供商 ──────────────────────────────────────────────

class GLMProvider(LLMProvider):
    """智谱AI (GLM) 提供商

    API文档: https://open.bigmodel.cn/dev/api
    默认模型: glm-4-flash
    """

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "glm-4-flash",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> None:
        config = ProviderConfig(
            api_key=api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4",
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        super().__init__(config)

    def get_provider_name(self) -> str:
        return "GLM(智谱)"


class QwenProvider(LLMProvider):
    """通义千问 (Qwen) 提供商

    API文档: https://help.aliyun.com/document_detail/2712195.html
    默认模型: qwen-plus
    """

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "qwen-plus",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> None:
        config = ProviderConfig(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        super().__init__(config)

    def get_provider_name(self) -> str:
        return "Qwen(通义)"


class DeepSeekProvider(LLMProvider):
    """DeepSeek 提供商

    API文档: https://platform.deepseek.com/api-docs
    默认模型: deepseek-chat
    """

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> None:
        config = ProviderConfig(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        super().__init__(config)

    def get_provider_name(self) -> str:
        return "DeepSeek"


# ── 工厂函数 ──────────────────────────────────────────────

PROVIDER_REGISTRY: dict[str, type[LLMProvider]] = {
    "glm": GLMProvider,
    "qwen": QwenProvider,
    "deepseek": DeepSeekProvider,
}


def create_provider(name: str, api_key: str = "", model_name: str = "", **kwargs: Any) -> LLMProvider:
    """根据名称创建LLM提供商实例

    Args:
        name: 提供商名称 (glm/qwen/deepseek)
        api_key: API密钥
        model_name: 模型名称

    Returns:
        LLMProvider 实例

    Raises:
        ValueError: 不支持的提供商名称
    """
    name_lower = name.lower().strip()
    if name_lower not in PROVIDER_REGISTRY:
        raise ValueError(
            f"不支持的LLM提供商: {name}，可选: {list(PROVIDER_REGISTRY.keys())}"
        )
    provider_cls = PROVIDER_REGISTRY[name_lower]
    if model_name:
        return provider_cls(api_key=api_key, model_name=model_name, **kwargs)
    return provider_cls(api_key=api_key, **kwargs)
