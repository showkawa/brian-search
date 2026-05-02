"""配置管理 — API Key与搜索条件

从 config.json 加载配置，支持:
- 多LLM提供商API Key管理
- 搜索条件默认值
- 模型选择配置
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── 默认配置路径 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent  # 项目根目录
DEFAULT_CONFIG_PATH = BASE_DIR / "brian_agent" / "cassiel_agent" / "config.json"


# ── 数据类 ──────────────────────────────────────────────

@dataclass
class SearchConfig:
    """搜索条件配置

    Attributes:
        keyword: 搜索关键词
        city: 城市名称
        city_code: BOSS直聘城市代码
        salary_min: 最低薪资(K)
        salary_max: 最高薪资(K)
        experience: 经验要求
        education: 学历要求
        max_pages: 最大抓取页数
        page_delay: 翻页间隔(秒)，遵守 G-04/G-08
    """

    keyword: str = "Python开发"
    city: str = "北京"
    city_code: str = "100010000"
    salary_min: int = 0
    salary_max: int = 0
    experience: str = "不限"
    education: str = "不限"
    max_pages: int = 3
    page_delay: float = 3.0  # G-08: 翻页间隔 ≥ 3s

    # 城市代码映射
    CITY_CODES: dict[str, str] = field(default_factory=lambda: {
        "北京": "100010000",
        "上海": "101020100",
        "深圳": "101280600",
        "杭州": "101210100",
        "广州": "101280100",
        "成都": "101270100",
        "南京": "101190100",
        "武汉": "101200100",
        "西安": "101110100",
        "重庆": "101040100",
    })

    def get_city_code(self) -> str:
        """获取城市代码"""
        return self.CITY_CODES.get(self.city, self.city_code)


@dataclass
class ModelConfig:
    """LLM模型配置

    每个环节可独立选择模型提供商和模型名称。

    Attributes:
        search_provider: 搜索环节使用的LLM提供商
        search_model: 搜索环节使用的模型名称
        evaluate_provider: 评估环节使用的LLM提供商
        evaluate_model: 评估环节使用的模型名称
        write_provider: 文案环节使用的LLM提供商
        write_model: 文案环节使用的模型名称
    """

    search_provider: str = "glm"
    search_model: str = "glm-4-flash"
    evaluate_provider: str = "deepseek"
    evaluate_model: str = "deepseek-chat"
    write_provider: str = "qwen"
    write_model: str = "qwen-plus"


@dataclass
class APIKeys:
    """API密钥配置

    Attributes:
        glm_key: 智谱AI API Key
        qwen_key: 通义千问 API Key
        deepseek_key: DeepSeek API Key
    """

    glm_key: str = ""
    qwen_key: str = ""
    deepseek_key: str = ""


@dataclass
class AppConfig:
    """应用总配置

    聚合所有子配置，支持从 config.json 加载。
    """

    search: SearchConfig = field(default_factory=SearchConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    api_keys: APIKeys = field(default_factory=APIKeys)

    @classmethod
    def from_json(cls, path: Path | str | None = None) -> AppConfig:
        """从JSON文件加载配置

        Args:
            path: 配置文件路径，默认使用 DEFAULT_CONFIG_PATH

        Returns:
            AppConfig 实例
        """
        config_path = Path(path) if path else DEFAULT_CONFIG_PATH
        if not config_path.exists():
            logger.warning("配置文件不存在: %s，使用默认配置", config_path)
            return cls()

        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("配置文件读取失败: %s", e)
            return cls()

        # 解析各子配置
        search_data = raw.get("search", {})
        model_data = raw.get("model", {})
        keys_data = raw.get("api_keys", {})

        return cls(
            search=SearchConfig(**{k: v for k, v in search_data.items() if k in SearchConfig.__dataclass_fields__}),
            model=ModelConfig(**{k: v for k, v in model_data.items() if k in ModelConfig.__dataclass_fields__}),
            api_keys=APIKeys(**{k: v for k, v in keys_data.items() if k in APIKeys.__dataclass_fields__}),
        )

    def to_json(self, path: Path | str | None = None) -> None:
        """保存配置到JSON文件

        Args:
            path: 配置文件路径，默认使用 DEFAULT_CONFIG_PATH
        """
        config_path = Path(path) if path else DEFAULT_CONFIG_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "search": self.search.__dict__,
            "model": self.model.__dict__,
            "api_keys": self.api_keys.__dict__,
        }
        config_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("配置已保存到: %s", config_path)

    def create_default_config(self, path: Path | str | None = None) -> None:
        """创建默认配置文件模板"""
        self.to_json(path)
