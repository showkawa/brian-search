"""邀约文案生成器 — LLM个性化邀约文本

使用大语言模型:
- 根据候选人信息和岗位JD生成个性化邀约文案
- 支持多种语气风格 (正式/亲切/专业)
- 人工预览确认后发送
"""

from __future__ import annotations

import logging
from typing import Any

from cassiel.config.settings import SearchConfig
from cassiel.llm.providers import LLMProvider
from cassiel.models.candidate import Candidate

logger = logging.getLogger(__name__)

# ── 文案生成提示词 ──────────────────────────────────────────────

WRITER_SYSTEM_PROMPT = """你是一位专业的HR招聘文案撰写助手。你的任务是根据候选人信息和岗位需求，
撰写个性化的沟通邀约文案。

文案要求:
1. 称呼候选人姓名
2. 简要介绍公司/岗位亮点
3. 提及候选人背景中与岗位匹配的亮点
4. 表达诚意，邀请进一步沟通
5. 语气{style}，字数100-200字
6. 不要使用过于模板化的表达

直接输出邀约文案，不要加标题或额外格式。"""

WRITER_USER_PROMPT = """## 岗位信息
- 职位: {keyword}
- 城市: {city}
- 薪资范围: {salary_min}K-{salary_max}K
- 经验要求: {experience}
- 学历要求: {education}

## 候选人信息
- 姓名: {name}
- 当前职位: {title}
- 当前薪资: {salary}
- 工作经验: {experience_info}
- 学历: {education_info}
- 当前公司: {company}
- 匹配度评分: {score}分
- 评分理由: {score_reason}

请撰写个性化的沟通邀约文案。"""


# ── 语气风格 ──────────────────────────────────────────────

class WritingStyle:
    """文案语气风格"""
    FORMAL = "正式专业"
    FRIENDLY = "亲切自然"
    PROFESSIONAL = "简洁高效"


class InvitationWriter:
    """邀约文案生成器

    使用LLM根据候选人信息生成个性化邀约文案。

    Usage:
        writer = InvitationWriter(provider=llm_provider)
        text = writer.generate(candidate, search_config)
    """

    def __init__(self, provider: LLMProvider) -> None:
        """初始化文案生成器

        Args:
            provider: LLM提供商实例
        """
        self.provider = provider

    def generate(
        self,
        candidate: Candidate,
        config: SearchConfig,
        style: str = WritingStyle.FRIENDLY,
    ) -> str:
        """生成个性化邀约文案

        Args:
            candidate: 候选人信息
            config: 搜索条件配置
            style: 文案语气风格

        Returns:
            生成的邀约文案
        """
        system_prompt = WRITER_SYSTEM_PROMPT.format(style=style)
        user_prompt = WRITER_USER_PROMPT.format(
            keyword=config.keyword,
            city=config.city,
            salary_min=config.salary_min,
            salary_max=config.salary_max,
            experience=config.experience,
            education=config.education,
            name=candidate.name or "候选人",
            title=candidate.title,
            salary=candidate.salary,
            experience_info=candidate.experience,
            education_info=candidate.education,
            company=candidate.company,
            score=candidate.score or "N/A",
            score_reason=candidate.score_reason or "综合评估",
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            text = self.provider.chat(messages=messages)
            logger.info("邀约文案已生成: %s (长度: %d)", candidate.name, len(text))
            return text.strip()
        except Exception as e:
            logger.error("生成邀约文案失败: %s", e)
            return f"文案生成失败，请手动撰写。错误: {e}"

    def generate_batch(
        self,
        candidates: list[Candidate],
        config: SearchConfig,
        style: str = WritingStyle.FRIENDLY,
        on_progress: Any | None = None,
    ) -> dict[str, str]:
        """批量生成邀约文案

        Args:
            candidates: 候选人列表
            config: 搜索条件
            style: 文案语气风格
            on_progress: 进度回调

        Returns:
            {候选人姓名: 邀约文案} 字典
        """
        results: dict[str, str] = {}
        total = len(candidates)

        for idx, candidate in enumerate(candidates):
            text = self.generate(candidate, config, style)
            key = candidate.name or f"候选人_{idx + 1}"
            results[key] = text

            if on_progress:
                on_progress(idx + 1, total)

        logger.info("批量生成完成: %d 条文案", len(results))
        return results
