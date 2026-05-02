"""E2E tests for Cassiel Agent pipeline — simulated data, no real network calls.

Tests cover:
- CandidateList model (add, sort, top_n)
- SearchConfig validation
- Pipeline DAG construction (3 stages)
- Orchestrator with simulated candidates
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from cassiel.agent.orchestrator import (
    Orchestrator,
    Pipeline,
    PipelineResult,
    PipelineStage,
    PipelineStep,
)
from cassiel.agent.roles import EVALUATOR_ROLE, SEARCHER_ROLE, WRITER_ROLE
from cassiel.config.settings import AppConfig, SearchConfig
from cassiel.models.candidate import Candidate, CandidateList


# ═══════════════════════════════════════════════════════════════
# Simulated candidate data (mirrors main.py _SIMULATED_CANDIDATES)
# ═══════════════════════════════════════════════════════════════

SIMULATED_CANDIDATES: list[dict[str, Any]] = [
    {
        "name": "张伟",
        "title": "高级前端工程师",
        "salary": "30-40K",
        "experience": "6年",
        "education": "本科",
        "company": "某科技公司",
        "online_status": "今日活跃",
    },
    {
        "name": "李娜",
        "title": "全栈开发工程师",
        "salary": "25-35K",
        "experience": "4年",
        "education": "硕士",
        "company": "某互联网公司",
        "online_status": "在线",
    },
    {
        "name": "王磊",
        "title": "前端架构师",
        "salary": "40-55K",
        "experience": "8年",
        "education": "本科",
        "company": "某金融科技公司",
        "online_status": "今日活跃",
    },
    {
        "name": "赵敏",
        "title": "React 开发工程师",
        "salary": "20-30K",
        "experience": "3年",
        "education": "本科",
        "company": "某创业公司",
        "online_status": "3天前活跃",
    },
    {
        "name": "陈晨",
        "title": "前端技术专家",
        "salary": "35-50K",
        "experience": "7年",
        "education": "硕士",
        "company": "某大厂",
        "online_status": "今日活跃",
    },
]


def _make_candidate_list() -> CandidateList:
    """Build a CandidateList from simulated data."""
    cl = CandidateList(search_keyword="Python开发", search_city="北京")
    for sample in SIMULATED_CANDIDATES:
        cl.add(Candidate(**sample))
    return cl


def _make_scored_candidate_list() -> CandidateList:
    """Build a CandidateList with scores assigned."""
    cl = _make_candidate_list()
    scores = [92, 85, 78, 65, 88]
    for candidate, score in zip(cl.candidates, scores):
        candidate.score = score
        candidate.score_reason = f"匹配度评分 {score}"
    return cl


# ═══════════════════════════════════════════════════════════════
# Test: CandidateList model
# ═══════════════════════════════════════════════════════════════


class TestCandidateList:
    """Tests for CandidateList add / sort / top_n."""

    def test_add_increments_count(self) -> None:
        cl = CandidateList()
        assert cl.total_count == 0

        cl.add(Candidate(name="Alice", title="Engineer"))
        assert cl.total_count == 1
        assert len(cl.candidates) == 1

        cl.add(Candidate(name="Bob", title="Designer"))
        assert cl.total_count == 2

    def test_sort_by_score_descending(self) -> None:
        cl = CandidateList()
        cl.add(Candidate(name="A", score=50))
        cl.add(Candidate(name="B", score=90))
        cl.add(Candidate(name="C", score=70))

        cl.sort_by_score(descending=True)
        names = [c.name for c in cl.candidates]
        assert names == ["B", "C", "A"]

    def test_sort_by_score_ascending(self) -> None:
        cl = CandidateList()
        cl.add(Candidate(name="A", score=50))
        cl.add(Candidate(name="B", score=90))
        cl.add(Candidate(name="C", score=70))

        cl.sort_by_score(descending=False)
        names = [c.name for c in cl.candidates]
        assert names == ["A", "C", "B"]

    def test_sort_handles_none_scores(self) -> None:
        cl = CandidateList()
        cl.add(Candidate(name="A", score=80))
        cl.add(Candidate(name="B"))  # score=None
        cl.add(Candidate(name="C", score=60))

        cl.sort_by_score(descending=True)
        names = [c.name for c in cl.candidates]
        # None scores sort to the end (treated as -1)
        assert names == ["A", "C", "B"]

    def test_top_n_returns_highest(self) -> None:
        cl = _make_scored_candidate_list()
        top3 = cl.top_n(3)
        assert len(top3) == 3
        assert top3[0].name == "张伟"  # score 92
        assert top3[1].name == "陈晨"  # score 88
        assert top3[2].name == "李娜"  # score 85

    def test_top_n_more_than_available(self) -> None:
        cl = _make_scored_candidate_list()
        top10 = cl.top_n(10)
        assert len(top10) == 5  # only 5 candidates exist

    def test_empty_list_top_n(self) -> None:
        cl = CandidateList()
        assert cl.top_n(3) == []


# ═══════════════════════════════════════════════════════════════
# Test: SearchConfig validation
# ═══════════════════════════════════════════════════════════════


class TestSearchConfig:
    """Tests for SearchConfig defaults and city code lookup."""

    def test_defaults(self) -> None:
        cfg = SearchConfig()
        assert cfg.keyword == "Python开发"
        assert cfg.city == "北京"
        assert cfg.salary_min == 0
        assert cfg.salary_max == 0
        assert cfg.experience == "不限"
        assert cfg.education == "不限"
        assert cfg.max_pages == 3
        assert cfg.page_delay >= 3.0  # G-08 compliance

    def test_custom_values(self) -> None:
        cfg = SearchConfig(
            keyword="前端开发",
            city="上海",
            salary_min=20,
            salary_max=40,
            experience="3-5年",
            education="本科",
        )
        assert cfg.keyword == "前端开发"
        assert cfg.city == "上海"
        assert cfg.salary_min == 20
        assert cfg.salary_max == 40

    def test_get_city_code_known_city(self) -> None:
        cfg = SearchConfig(city="上海")
        assert cfg.get_city_code() == "101020100"

    def test_get_city_code_unknown_city(self) -> None:
        cfg = SearchConfig(city="未知城市", city_code="999999999")
        assert cfg.get_city_code() == "999999999"

    def test_city_codes_populated(self) -> None:
        cfg = SearchConfig()
        assert len(cfg.CITY_CODES) >= 10


# ═══════════════════════════════════════════════════════════════
# Test: Pipeline DAG construction
# ═══════════════════════════════════════════════════════════════


class TestPipelineDAG:
    """Tests for Pipeline stage registration and DAG topology."""

    def test_three_stages_created(self) -> None:
        """Verify the default pipeline has exactly 3 stages."""
        pipeline = Pipeline(name="test-pipeline")

        pipeline.add_stage(PipelineStage(
            name="搜索候选人",
            fn=lambda **kw: _make_candidate_list(),
            role=SEARCHER_ROLE,
        ))
        pipeline.add_stage(PipelineStage(
            name="评估筛选",
            fn=lambda **kw: _make_scored_candidate_list(),
            role=EVALUATOR_ROLE,
        ), depends_on=["搜索候选人"])
        pipeline.add_stage(PipelineStage(
            name="生成邀约",
            fn=lambda **kw: {"张伟": "邀约文案"},
            role=WRITER_ROLE,
        ), depends_on=["评估筛选"])

        assert len(pipeline._order) == 3
        assert pipeline._order == ["搜索候选人", "评估筛选", "生成邀约"]

    def test_stage_roles_correct(self) -> None:
        """Verify each stage has the correct AgentRole."""
        pipeline = Pipeline(name="test-pipeline")

        pipeline.add_stage(PipelineStage(
            name="搜索候选人",
            fn=lambda **kw: _make_candidate_list(),
            role=SEARCHER_ROLE,
        ))
        pipeline.add_stage(PipelineStage(
            name="评估筛选",
            fn=lambda **kw: _make_scored_candidate_list(),
            role=EVALUATOR_ROLE,
        ), depends_on=["搜索候选人"])
        pipeline.add_stage(PipelineStage(
            name="生成邀约",
            fn=lambda **kw: {},
            role=WRITER_ROLE,
        ), depends_on=["评估筛选"])

        stages = pipeline._stage_registry
        assert stages["搜索候选人"][0].role.name == "搜索员"
        assert stages["评估筛选"][0].role.name == "评估员"
        assert stages["生成邀约"][0].role.name == "文案员"

    def test_pipeline_run_with_simulated_data(self) -> None:
        """Run the full pipeline with simulated data — no real network calls."""
        pipeline = Pipeline(name="test-pipeline")

        # Stage 1: search → CandidateList
        pipeline.add_stage(PipelineStage(
            name="搜索候选人",
            fn=lambda **kw: _make_candidate_list(),
            role=SEARCHER_ROLE,
        ))

        # Stage 2: evaluate → scored CandidateList
        pipeline.add_stage(PipelineStage(
            name="评估筛选",
            fn=lambda **kw: _make_scored_candidate_list(),
            role=EVALUATOR_ROLE,
        ), depends_on=["搜索候选人"])

        # Stage 3: write → invitation dict
        def _fake_write(**kw: Any) -> dict[str, str]:
            candidates = kw.get("评估筛选")
            if candidates is None:
                return {}
            cl = candidates if isinstance(candidates, CandidateList) else CandidateList()
            return {c.name: f"你好{c.name}，诚邀沟通" for c in cl.candidates[:3]}

        pipeline.add_stage(PipelineStage(
            name="生成邀约",
            fn=_fake_write,
            role=WRITER_ROLE,
        ), depends_on=["评估筛选"])

        result = pipeline.run(search_config=SearchConfig())

        assert isinstance(result, PipelineResult)
        assert len(result.steps) == 3
        assert all(s.status == "completed" for s in result.steps)
        assert result.candidates.total_count == 5
        assert len(result.invitations) == 3
        assert "张伟" in result.invitations

    def test_pipeline_dependency_skip_on_failure(self) -> None:
        """If a stage fails, dependent stages should be skipped."""
        pipeline = Pipeline(name="test-failure")

        def _failing_stage(**kw: Any) -> CandidateList:
            raise RuntimeError("模拟搜索失败")

        pipeline.add_stage(PipelineStage(
            name="搜索候选人",
            fn=_failing_stage,
            role=SEARCHER_ROLE,
            max_retries=1,
        ))
        pipeline.add_stage(PipelineStage(
            name="评估筛选",
            fn=lambda **kw: _make_scored_candidate_list(),
            role=EVALUATOR_ROLE,
        ), depends_on=["搜索候选人"])

        result = pipeline.run(search_config=SearchConfig())

        assert result.steps[0].status == "failed"
        assert result.steps[1].status == "skipped"


# ═══════════════════════════════════════════════════════════════
# Test: Orchestrator with simulated candidates
# ═══════════════════════════════════════════════════════════════


class TestOrchestratorSimulated:
    """Tests for Orchestrator using simulated data (mocked network)."""

    @patch("cassiel.agent.orchestrator.BossCollector")
    @patch("cassiel.agent.orchestrator.CandidateFilter")
    @patch("cassiel.agent.orchestrator.InvitationWriter")
    @patch("cassiel.agent.orchestrator.create_provider")
    @patch("cassiel.agent.orchestrator.SessionStore")
    def test_orchestrator_run_with_simulated(
        self,
        mock_store_cls: MagicMock,
        mock_create_provider: MagicMock,
        mock_writer_cls: MagicMock,
        mock_filter_cls: MagicMock,
        mock_collector_cls: MagicMock,
    ) -> None:
        """Full orchestrator run with all external calls mocked."""
        # Setup mocks
        mock_store = MagicMock()
        mock_store.__enter__ = MagicMock(return_value=mock_store)
        mock_store.__exit__ = MagicMock(return_value=False)
        mock_store_cls.return_value = mock_store

        mock_provider = MagicMock()
        mock_create_provider.return_value = mock_provider

        # Mock collector
        mock_collector = MagicMock()
        mock_collector.__enter__ = MagicMock(return_value=mock_collector)
        mock_collector.__exit__ = MagicMock(return_value=False)
        mock_collector.search.return_value = _make_candidate_list()
        mock_collector_cls.return_value = mock_collector

        # Mock filter
        mock_filter = MagicMock()
        mock_filter.evaluate.return_value = _make_scored_candidate_list()
        mock_filter_cls.return_value = mock_filter

        # Mock writer
        mock_writer = MagicMock()
        mock_writer.generate_batch.return_value = {
            "张伟": "你好张伟，诚邀沟通",
            "陈晨": "你好陈晨，期待交流",
        }
        mock_writer_cls.return_value = mock_writer

        # Run
        config = AppConfig()
        config.api_keys.glm_key = "fake-glm-key"
        config.api_keys.deepseek_key = "fake-deepseek-key"
        config.api_keys.qwen_key = "fake-qwen-key"

        orchestrator = Orchestrator(config=config)
        result = orchestrator.run(search_config=SearchConfig())

        assert isinstance(result, PipelineResult)
        assert result.candidates.total_count == 5
        assert len(result.invitations) >= 1

    def test_orchestrator_steps_defined(self) -> None:
        """Orchestrator should define 3 pipeline steps."""
        config = AppConfig()
        orchestrator = Orchestrator(config=config)
        assert len(orchestrator.steps) == 3
        assert orchestrator.steps[0].name == "搜索候选人"
        assert orchestrator.steps[1].name == "评估筛选"
        assert orchestrator.steps[2].name == "生成邀约"
