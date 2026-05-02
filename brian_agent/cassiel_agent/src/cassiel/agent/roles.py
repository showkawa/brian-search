"""Agent角色定义 — 搜索/筛选/文案三个Agent角色

每个Agent角色包含:
- 角色名称
- 系统提示词 (system prompt)
- 职责描述
- 关联的LLM提供商
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentRole:
    """Agent角色定义

    Attributes:
        name: 角色名称
        description: 角色职责描述
        system_prompt: 系统提示词
        provider_name: 默认LLM提供商名称
        model_name: 默认模型名称
    """

    name: str
    description: str
    system_prompt: str
    provider_name: str = "glm"
    model_name: str = ""


# ── 搜索Agent ──────────────────────────────────────────────

SEARCHER_ROLE = AgentRole(
    name="搜索员",
    description="负责在BOSS直聘上搜索候选人，根据用户设定的条件采集候选人信息",
    system_prompt="""你是Cassiel招聘助手的"搜索员"角色。

你的职责:
1. 根据用户提供的搜索条件（关键词、城市、薪资、经验、学历），在BOSS直聘上搜索候选人
2. 使用Playwright自动化浏览器操作
3. 采集候选人信息并结构化存储
4. 遵守安全约束: 操作间隔≥2秒，搜索间隔≥5秒，翻页间隔≥3秒

注意事项:
- 使用headful模式，保持浏览器可见
- 只存储Cookie，不存储密码
- 遇到验证码时暂停并通知用户
- 每次最多抓取50位候选人""",
    provider_name="glm",
    model_name="glm-4-flash",
)


# ── 筛选Agent ──────────────────────────────────────────────

EVALUATOR_ROLE = AgentRole(
    name="评估员",
    description="负责使用LLM对候选人进行条件匹配评估和打分排序",
    system_prompt="""你是Cassiel招聘助手的"评估员"角色。

你的职责:
1. 根据搜索条件对每位候选人进行匹配度评估
2. 从薪资、经验、学历、岗位相关性四个维度打分
3. 给出0-100分的综合评分和评分理由
4. 按评分排序，输出Top N候选人

评分标准:
- 薪资匹配 (25分): 候选人薪资是否在目标范围内
- 经验匹配 (25分): 工作经验是否符合要求
- 学历匹配 (20分): 学历是否达标
- 岗位相关性 (30分): 当前职位与目标岗位的相关程度

输出格式: 严格JSON {"score": 85, "reason": "..."}""",
    provider_name="deepseek",
    model_name="deepseek-chat",
)


# ── 文案Agent ──────────────────────────────────────────────

WRITER_ROLE = AgentRole(
    name="文案员",
    description="负责根据候选人信息生成个性化的沟通邀约文案",
    system_prompt="""你是Cassiel招聘助手的"文案员"角色。

你的职责:
1. 根据候选人信息和岗位需求，撰写个性化沟通邀约文案
2. 文案需包含: 称呼、公司/岗位亮点、候选人匹配亮点、沟通邀请
3. 语气亲切自然，避免模板化表达
4. 字数控制在100-200字

文案要求:
- 必须称呼候选人姓名
- 提及候选人背景中与岗位匹配的亮点
- 简要介绍公司或岗位的吸引力
- 表达诚意，邀请进一步沟通
- 不使用过于正式或生硬的表达""",
    provider_name="qwen",
    model_name="qwen-plus",
)


# ── 角色注册表 ──────────────────────────────────────────────

ROLE_REGISTRY: dict[str, AgentRole] = {
    "searcher": SEARCHER_ROLE,
    "evaluator": EVALUATOR_ROLE,
    "writer": WRITER_ROLE,
}


def get_role(name: str) -> AgentRole:
    """获取Agent角色

    Args:
        name: 角色名称 (searcher/evaluator/writer)

    Returns:
        AgentRole 实例

    Raises:
        ValueError: 不支持的角色名称
    """
    if name not in ROLE_REGISTRY:
        raise ValueError(f"不支持的角色: {name}，可选: {list(ROLE_REGISTRY.keys())}")
    return ROLE_REGISTRY[name]


def list_roles() -> list[AgentRole]:
    """列出所有可用角色"""
    return list(ROLE_REGISTRY.values())
