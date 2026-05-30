"""候选人数据模型 — Pydantic v2 BaseModel

定义候选人信息的结构化数据模型，用于:
- 采集器输出标准化
- 评估器输入格式
- UI表格展示
- 会话持久化
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Candidate(BaseModel):
    """候选人信息模型

    Attributes:
        name: 候选人姓名
        title: 职位名称
        salary: 薪资范围 (如 "30-40K")
        experience: 工作经验 (如 "5年")
        education: 学历 (如 "本科")
        online_status: 在线状态 (如 "今日活跃")
        profile_url: 个人主页链接
        company: 当前公司
        raw_data: 原始采集数据 (保留完整信息)
    """

    name: str = Field(default="", description="候选人姓名")
    title: str = Field(default="", description="职位名称")
    salary: str = Field(default="", description="薪资范围")
    experience: str = Field(default="", description="工作经验")
    education: str = Field(default="", description="学历")
    online_status: str = Field(default="", description="在线状态")
    profile_url: str = Field(default="", description="个人主页链接")
    company: str = Field(default="", description="当前公司")
    raw_data: dict[str, Any] = Field(default_factory=dict, description="原始采集数据")

    # ── 评估结果 (由 evaluator 填充) ──
    score: float | None = Field(default=None, description="匹配度评分 (0-100)")
    score_reason: str = Field(default="", description="评分理由")
    is_selected: bool = Field(default=False, description="是否被选中")

    model_config = {"from_attributes": True}


class CandidateList(BaseModel):
    """候选人列表容器

    用于批量传递和序列化候选人数据。
    """

    candidates: list[Candidate] = Field(default_factory=list, description="候选人列表")
    total_count: int = Field(default=0, description="总数量")
    search_keyword: str = Field(default="", description="搜索关键词")
    search_city: str = Field(default="", description="搜索城市")

    def add(self, candidate: Candidate) -> None:
        """添加候选人"""
        self.candidates.append(candidate)
        self.total_count = len(self.candidates)

    def sort_by_score(self, descending: bool = True) -> None:
        """按评分排序"""
        self.candidates.sort(
            key=lambda c: c.score if c.score is not None else -1,
            reverse=descending,
        )

    def top_n(self, n: int) -> list[Candidate]:
        """获取评分最高的N个候选人"""
        self.sort_by_score()
        return self.candidates[:n]
