"""候选人筛选评估器 — LLM条件匹配与评分

使用大语言模型对候选人进行:
- 条件匹配度评估
- 综合打分 (0-100)
- 评分理由生成
- Top N 排序输出

错误处理:
- LLM 频率限制 → 指数退避重试
- LLM 超时 → 跳过候选人
- JSON 解析失败 → 回退到规则评分
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from cassiel.config.settings import SearchConfig
from cassiel.llm.providers import LLMProvider
from cassiel.models.candidate import Candidate, CandidateList

logger = logging.getLogger(__name__)

# ── 评估提示词模板 ──────────────────────────────────────────────

EVALUATE_SYSTEM_PROMPT = """你是一位专业的HR招聘评估助手。你的任务是根据给定的搜索条件，
对候选人进行匹配度评估和打分。

评分规则:
- 综合匹配度评分: 0-100分
- 评估维度: 薪资匹配、经验匹配、学历匹配、岗位相关性
- 必须给出评分理由

输出格式 (严格JSON):
{
  "score": 85,
  "reason": "薪资范围匹配，5年经验符合要求，本科学历达标，岗位高度相关"
}
"""

EVALUATE_USER_PROMPT = """## 搜索条件
- 关键词: {keyword}
- 城市: {city}
- 薪资范围: {salary_min}K-{salary_max}K
- 经验要求: {experience}
- 学历要求: {education}

## 候选人信息
- 姓名: {name}
- 职位: {title}
- 薪资: {salary}
- 经验: {experience_info}
- 学历: {education_info}
- 公司: {company}
- 在线状态: {online_status}

请评估该候选人与搜索条件的匹配度，给出评分和理由。"""


class CandidateFilter:
    """候选人筛选评估器

    使用LLM对候选人列表进行条件匹配评估和打分排序。

    Usage:
        filter = CandidateFilter(provider=llm_provider)
        scored = filter.evaluate(candidates, search_config)
        top5 = scored.top_n(5)
    """

    def __init__(self, provider: LLMProvider) -> None:
        """初始化评估器

        Args:
            provider: LLM提供商实例
        """
        self.provider = provider

    def evaluate(
        self,
        candidates: CandidateList,
        config: SearchConfig,
        on_progress: Any | None = None,
    ) -> CandidateList:
        """评估候选人列表

        逐个调用LLM评估候选人匹配度，填充score和score_reason字段。
        单个候选人评估失败不会中断整体流程，仅跳过该候选人。

        Args:
            candidates: 候选人列表
            config: 搜索条件配置
            on_progress: 进度回调 (current, total)

        Returns:
            评分后的候选人列表 (已按评分排序)
        """
        total = len(candidates.candidates)
        self._log(f"开始评估 {total} 位候选人...")
        failed_count = 0

        for idx, candidate in enumerate(candidates.candidates):
            for retry in range(3):  # 最多重试 3 次
                try:
                    result = self._evaluate_one(candidate, config)
                    candidate.score = result.get("score", 0)
                    candidate.score_reason = result.get("reason", "")
                    break  # 成功，退出重试循环
                except Exception as e:
                    err_str = str(e).lower()
                    if retry < 2 and ("rate" in err_str or "429" in err_str or "limit" in err_str):
                        # 频率限制 → 指数退避重试
                        delay = 2.0 * (2 ** retry)
                        logger.warning(
                            "[CandidateFilter] 频率限制 (%s)，%s 后重试 (%d/3)",
                            candidate.name, f"{delay:.0f}s", retry + 1,
                        )
                        time.sleep(delay)
                    elif retry < 2 and ("timeout" in err_str or "connect" in err_str):
                        # 网络错误 → 短暂重试
                        logger.warning(
                            "[CandidateFilter] 网络错误 (%s)，重试 (%d/3): %s",
                            candidate.name, retry + 1, e,
                        )
                        time.sleep(1.0)
                    else:
                        # 其他错误或重试耗尽 → 跳过该候选人
                        logger.warning(
                            "[CandidateFilter] 评估候选人 %s 失败 (已重试 %d 次): %s",
                            candidate.name, retry + 1, e,
                        )
                        candidate.score = 0
                        candidate.score_reason = f"评估失败: {e}"
                        failed_count += 1
                        break

            if on_progress:
                on_progress(idx + 1, total)

        # 按评分排序
        candidates.sort_by_score(descending=True)

        top_score = candidates.candidates[0].score if candidates.candidates else "N/A"
        self._log(
            f"评估完成: {total} 位, 失败 {failed_count}, 最高分: {top_score}"
        )
        return candidates

    def _evaluate_one(self, candidate: Candidate, config: SearchConfig) -> dict[str, Any]:
        """评估单个候选人

        Returns:
            {"score": int, "reason": str}
        """
        user_prompt = EVALUATE_USER_PROMPT.format(
            keyword=config.keyword,
            city=config.city,
            salary_min=config.salary_min,
            salary_max=config.salary_max,
            experience=config.experience,
            education=config.education,
            name=candidate.name,
            title=candidate.title,
            salary=candidate.salary,
            experience_info=candidate.experience,
            education_info=candidate.education,
            company=candidate.company,
            online_status=candidate.online_status,
        )

        messages = [
            {"role": "system", "content": EVALUATE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        result = self.provider.chat_json(messages=messages)

        # 确保返回格式正确
        score = result.get("score", 0)
        if isinstance(score, str):
            try:
                score = float(score)
            except ValueError:
                score = 0
        score = max(0, min(100, score))

        return {
            "score": score,
            "reason": result.get("reason", ""),
        }

    def filter_top_n(
        self,
        candidates: CandidateList,
        config: SearchConfig,
        n: int = 5,
        min_score: float = 60.0,
    ) -> CandidateList:
        """筛选Top N候选人

        Args:
            candidates: 候选人列表
            config: 搜索条件
            n: 返回数量
            min_score: 最低评分阈值

        Returns:
            符合条件的Top N候选人
        """
        scored = self.evaluate(candidates, config)
        # 过滤低分候选人
        qualified = CandidateList(
            search_keyword=scored.search_keyword,
            search_city=scored.search_city,
        )
        for c in scored.candidates:
            if c.score is not None and c.score >= min_score:
                c.is_selected = True
                qualified.add(c)
        return CandidateList(
            candidates=qualified.top_n(n),
            search_keyword=scored.search_keyword,
            search_city=scored.search_city,
        )

    @staticmethod
    def _log(msg: str) -> None:
        logger.info("[CandidateFilter] %s", msg)
