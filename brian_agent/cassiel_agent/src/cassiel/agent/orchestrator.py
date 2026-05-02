"""Agent流水线编排 — 搜索→筛选→文案 DAG编排

将三个Agent角色串联为流水线:
1. 搜索Agent: 采集候选人
2. 筛选Agent: 评估打分排序
3. 文案Agent: 生成邀约文案

编排器管理:
- MS-Agent风格 DAG 流水线: 有向无环图阶段链
- 阶段间类型化状态传递
- 错误处理与指数退避重试
- 熔断器保护
- 进度与日志回调

架构:
  Pipeline (DAG引擎)
    ├── Stage 1: BossCollector.search()   → CandidateList
    ├── Stage 2: CandidateFilter.evaluate() → CandidateList (scored)
    └── Stage 3: InvitationWriter.generate_batch() → dict[name, text]
"""

from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Generic, TypeVar

from cassiel.agent.roles import EVALUATOR_ROLE, SEARCHER_ROLE, WRITER_ROLE, AgentRole
from cassiel.collector.boss import BossCollector
from cassiel.config.settings import AppConfig, SearchConfig
from cassiel.evaluator.filter import CandidateFilter
from cassiel.llm.providers import LLMProvider, create_provider
from cassiel.models.candidate import Candidate, CandidateList
from cassiel.session.store import SessionStore
from cassiel.writer.invitation import InvitationWriter

logger = logging.getLogger(__name__)


# ── 类型变量 (用于泛型阶段输入/输出) ────────────────────────────

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")

# ── 流水线状态 ──────────────────────────────────────────────

class StepStatus(Enum):
    """步骤状态枚举"""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass
class PipelineStep:
    """流水线步骤

    Attributes:
        name: 步骤名称
        role: 关联的Agent角色
        status: 步骤状态
        message: 状态消息
        duration_ms: 执行耗时 (毫秒)
        retries: 已重试次数
    """

    name: str
    role: AgentRole
    status: str = "pending"
    message: str = ""
    duration_ms: float = 0.0
    retries: int = 0


@dataclass
class PipelineResult:
    """流水线执行结果

    Attributes:
        candidates: 候选人列表
        invitations: 邀约文案 {候选人姓名: 文案}
        steps: 各步骤执行状态
        search_id: 搜索记录ID
        total_duration_ms: 总耗时
    """

    candidates: CandidateList = field(default_factory=CandidateList)
    invitations: dict[str, str] = field(default_factory=dict)
    steps: list[PipelineStep] = field(default_factory=list)
    search_id: int = 0
    total_duration_ms: float = 0.0

    @property
    def success(self) -> bool:
        """所有步骤是否完成"""
        return all(s.status == "completed" for s in self.steps if s.status != "skipped")


# ── 流水线 DAG 阶段定义 ────────────────────────────────────────

class PipelineStage(Generic[InputT, OutputT]):
    """MS-Agent风格流水线阶段

    代表 DAG 中的一个节点，接收 InputT，产出 OutputT。
    通过 stages 链串联形成有向无环图。

    Usage:
        stage = PipelineStage(
            name="搜索阶段",
            fn=collector.search,
            role=SEARCHER_ROLE,
            max_retries=2,
        )
    """

    def __init__(
        self,
        name: str,
        fn: Callable[..., OutputT],
        role: AgentRole,
        max_retries: int = 1,
        timeout_ms: float = 0,
        retry_delay_base: float = 2.0,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        self.name = name
        self.fn = fn
        self.role = role
        self.max_retries = max_retries
        self.timeout_ms = timeout_ms
        self.retry_delay_base = retry_delay_base
        self._on_log = on_log or (lambda _: None)

    def execute(self, *args: Any, **kwargs: Any) -> OutputT:
        """执行阶段，带重试和指数退避
        """
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return self.fn(*args, **kwargs)
            except Exception as e:
                last_err = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay_base * (2 ** attempt)
                    self._on_log(
                        f"⚠️ [{self.name}] 失败，{delay:.1f}s 后重试 ({attempt + 1}/{self.max_retries}): {e}"
                    )
                    time.sleep(delay)
                else:
                    self._on_log(f"❌ [{self.name}] 重试耗尽 ({self.max_retries}次): {e}")
        raise last_err  # type: ignore[misc]


# ── 流水线 DAG 引擎 ────────────────────────────────────────

class Pipeline:
    """MS-Agent风格 DAG 流水线引擎

    将有向无环图中的阶段按拓扑序执行，自动传递中间状态。

    架构:
      Pipeline (DAG引擎)
        ├─ Stage 1: BossCollector.search(config)       → CandidateList
        ├─ Stage 2: CandidateFilter.evaluate(candidates, config) → CandidateList
        └─ Stage 3: InvitationWriter.generate_batch(candidates, config) → dict

    Usage:
        pipeline = Pipeline("招聘流水线", on_log=log_callback)
        pipeline.add_stage(search_stage, depends_on=[])
        pipeline.add_stage(evaluate_stage, depends_on=[search_stage])
        pipeline.add_stage(write_stage, depends_on=[evaluate_stage])
        result = pipeline.run(search_config=config)
    """

    def __init__(
        self,
        name: str = "Cassiel Pipeline",
        on_log: Callable[[str], None] | None = None,
        on_progress: Callable[[str, float], None] | None = None,
    ) -> None:
        self.name = name
        self.on_log = on_log or (lambda msg: logger.info(msg))
        self.on_progress = on_progress or (lambda s, p: None)

        # 存储阶段元信息: {stage_name: (stage, depends_on, status)}
        self._stage_registry: dict[
            str, tuple[PipelineStage, list[str], PipelineStep]
        ] = {}
        self._order: list[str] = []  # 拓扑序

    def add_stage(
        self,
        stage: PipelineStage,
        depends_on: list[str] | None = None,
    ) -> Pipeline:
        """添加流水线阶段

        Args:
            stage: 阶段定义
            depends_on: 依赖的前置阶段名称列表 (DAG边)

        Returns:
            self (链式调用)
        """
        deps = depends_on or []
        # 自动推导拓扑序: 如果依赖为空，追加到末尾; 否则插入到最后一个依赖之后
        insert_idx = 0
        for dep in deps:
            if dep in self._order:
                dep_idx = self._order.index(dep)
                insert_idx = max(insert_idx, dep_idx + 1)

        if stage.name in self._order:
            self._order.remove(stage.name)
        self._order.insert(insert_idx, stage.name)

        step = PipelineStep(name=stage.name, role=stage.role)
        self._stage_registry[stage.name] = (stage, deps, step)
        logger.debug("Pipeline[%s] + stage: %s (deps: %s)", self.name, stage.name, deps)
        return self

    # ── 执行 ──────────────────────────────────────────────

    def run(self, **shared_input: Any) -> PipelineResult:
        """按拓扑序执行所有阶段

        各阶段从 shared_state 读取输入，将输出写回 shared_state。
        后续阶段从 shared_state 读取前驱输出。

        Args:
            **shared_input: 共享输入 (如 search_config, config 等)

        Returns:
            PipelineResult 聚合结果
        """
        self._log("=" * 50)
        self._log(f"🚀 {self.name} 启动 (共 {len(self._order)} 个阶段)")
        self._log("=" * 50)

        shared_state: dict[str, Any] = dict(shared_input)
        steps: list[PipelineStep] = []
        start_time = time.monotonic()

        total_stages = len(self._order)
        for idx, stage_name in enumerate(self._order):
            stage, deps, step = self._stage_registry[stage_name]

            # 检查依赖是否都已完成
            if not self._deps_satisfied(stage_name, steps):
                step.status = "skipped"
                step.message = "前置阶段失败，跳过"
                self._log(f"⏭ {stage_name}: {step.message}")
                steps.append(step)
                continue

            self._log(f"\n📌 [{idx + 1}/{total_stages}] {stage_name}")
            step.status = "running"
            t0 = time.monotonic()

            try:
                output = stage.execute(
                    **shared_state,
                )
                duration = (time.monotonic() - t0) * 1000

                # 将输出注入共享状态
                shared_state[stage_name] = output
                step.status = "completed"
                step.duration_ms = duration
                step.message = f"完成 ({duration:.0f}ms)"
                self._log(f"✅ {stage_name}: {step.message}")

            except Exception as e:
                duration = (time.monotonic() - t0) * 1000
                step.status = "failed"
                step.duration_ms = duration
                step.message = str(e)
                self._log(f"❌ {stage_name} 失败 ({duration:.0f}ms): {e}")
                traceback.print_exc()

            steps.append(step)
            self.on_progress(stage_name, (idx + 1) / total_stages)

        total_duration = (time.monotonic() - start_time) * 1000
        self._log(f"\n🏁 {self.name} 完成 ({total_duration:.0f}ms)")

        return self._build_result(shared_state, steps, total_duration)

    def _deps_satisfied(self, stage_name: str, completed_steps: list[PipelineStep]) -> bool:
        """检查前置依赖是否都已完成"""
        _, deps, _ = self._stage_registry[stage_name]
        step_map = {s.name: s for s in completed_steps}
        for dep in deps:
            dep_step = step_map.get(dep)
            if dep_step is None or dep_step.status == "failed":
                return False
        return True

    def _build_result(
        self,
        shared_state: dict[str, Any],
        steps: list[PipelineStep],
        total_duration_ms: float,
    ) -> PipelineResult:
        """从共享状态和步骤列表构建 PipelineResult"""
        # 提取 candidates (从第一个产出 CandidateList 的阶段)
        candidates = CandidateList()
        invitations: dict[str, str] = {}

        for stage_name in self._order:
            val = shared_state.get(stage_name)
            if isinstance(val, CandidateList):
                candidates = val
            elif isinstance(val, dict):
                # 可能是 invitations dict
                if val and all(isinstance(k, str) and isinstance(v, str) for k, v in val.items()):
                    invitations = val  # type: ignore[assignment]

        return PipelineResult(
            candidates=candidates,
            invitations=invitations,
            steps=steps,
            total_duration_ms=total_duration_ms,
        )

    def _log(self, msg: str) -> None:
        self.on_log(msg)


# ── 便捷构造器 ────────────────────────────────────────────

def create_default_pipeline(
    config: AppConfig,
    on_log: Callable[[str], None] | None = None,
) -> Pipeline:
    """创建默认的三阶段招聘流水线

    串联:
      1. BossCollector.search()
      2. CandidateFilter.evaluate()
      3. InvitationWriter.generate_batch()
    """
    log = on_log or (lambda _: None)
    model_cfg = config.model
    api_keys = config.api_keys

    # 初始化 LLM 提供商
    eval_provider = create_provider(
        model_cfg.evaluate_provider,
        api_key=getattr(api_keys, f"{model_cfg.evaluate_provider}_key", ""),
        model_name=model_cfg.evaluate_model,
    ) if getattr(api_keys, f"{model_cfg.evaluate_provider}_key", "") else None

    write_provider = create_provider(
        model_cfg.write_provider,
        api_key=getattr(api_keys, f"{model_cfg.write_provider}_key", ""),
        model_name=model_cfg.write_model,
    ) if getattr(api_keys, f"{model_cfg.write_provider}_key", "") else None

    pipeline = Pipeline(name="Cassiel 招聘流水线", on_log=log)

    # ── Stage 1: 搜索 ──
    def _stage_search(**kw: Any) -> CandidateList:
        search_config = kw.get("search_config")
        if search_config is None:
            raise ValueError("缺少 search_config 参数")
        with BossCollector(on_log=log) as collector:
            return collector.search(config=search_config)

    pipeline.add_stage(PipelineStage(
        name="搜索候选人",
        fn=_stage_search,
        role=SEARCHER_ROLE,
        max_retries=1,
    ))

    # ── Stage 2: 评估筛选 ──
    def _stage_evaluate(**kw: Any) -> CandidateList:
        search_config = kw.get("search_config")
        candidates = kw.get("搜索候选人")
        if candidates is None:
            raise ValueError("缺少 搜索候选人 的输出")
        if eval_provider is None:
            raise RuntimeError("评估 LLM 提供商未配置")
        evaluator = CandidateFilter(provider=eval_provider)
        return evaluator.evaluate(candidates, search_config)

    pipeline.add_stage(PipelineStage(
        name="评估筛选",
        fn=_stage_evaluate,
        role=EVALUATOR_ROLE,
        max_retries=2,
    ), depends_on=["搜索候选人"])

    # ── Stage 3: 生成邀约 ──
    def _stage_write(**kw: Any) -> dict[str, str]:
        search_config = kw.get("search_config")
        candidates = kw.get("评估筛选")
        if candidates is None:
            raise ValueError("缺少 评估筛选 的输出")
        if write_provider is None:
            raise RuntimeError("文案 LLM 提供商未配置")
        writer = InvitationWriter(provider=write_provider)
        # candidates is CandidateList, get top candidates
        candidate_list = candidates.candidates if isinstance(candidates, CandidateList) else []
        return writer.generate_batch(candidate_list, search_config)

    pipeline.add_stage(PipelineStage(
        name="生成邀约",
        fn=_stage_write,
        role=WRITER_ROLE,
        max_retries=1,
    ), depends_on=["评估筛选"])

    return pipeline


# ── 兼容层: Orchestrator (保持向后兼容) ──────────────────────

class Orchestrator:
    """流水线编排器 (兼容旧接口)

    内部使用 Pipeline DAG 引擎执行。

    Usage:
        orchestrator = Orchestrator(config=app_config)
        result = orchestrator.run(search_config)
    """

    def __init__(
        self,
        config: AppConfig,
        on_log: Callable[[str], None] | None = None,
        on_progress: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """初始化编排器

        Args:
            config: 应用配置
            on_log: 日志回调
            on_progress: 进度回调 (step_name, current, total)
        """
        self.config = config
        self.on_log = on_log or (lambda msg: logger.info(msg))
        self.on_progress = on_progress or (lambda s, c, t: None)

        # 创建LLM提供商
        self._providers: dict[str, LLMProvider] = {}
        self._init_providers()

        # 流水线步骤定义 (兼容旧接口)
        self.steps = [
            PipelineStep(name="搜索候选人", role=SEARCHER_ROLE),
            PipelineStep(name="评估筛选", role=EVALUATOR_ROLE),
            PipelineStep(name="生成邀约", role=WRITER_ROLE),
        ]

    def _init_providers(self) -> None:
        """初始化LLM提供商实例"""
        api_keys = self.config.api_keys
        model_cfg = self.config.model

        provider_configs = {
            "glm": (api_keys.glm_key, model_cfg.search_model),
            "qwen": (api_keys.qwen_key, model_cfg.write_model),
            "deepseek": (api_keys.deepseek_key, model_cfg.evaluate_model),
        }

        for name, (key, model) in provider_configs.items():
            if key:
                self._providers[name] = create_provider(name, api_key=key, model_name=model)
                self._log(f"✅ LLM提供商已初始化: {name}")
            else:
                self._log(f"⚠️ LLM提供商 {name} 未配置API Key")

    def _get_provider(self, provider_name: str) -> LLMProvider:
        """获取LLM提供商"""
        if provider_name not in self._providers:
            raise ValueError(f"LLM提供商 {provider_name} 未初始化，请检查API Key配置")
        return self._providers[provider_name]

    def _log(self, msg: str) -> None:
        """输出日志"""
        self.on_log(msg)

    # ── 流水线执行 ──────────────────────────────────────────────

    def run(
        self,
        search_config: SearchConfig,
        top_n: int = 5,
        min_score: float = 60.0,
        max_pages: int = 3,
    ) -> PipelineResult:
        """执行完整流水线

        使用内部 DAG Pipeline 引擎或回退到手动步骤执行。

        Args:
            search_config: 搜索条件
            top_n: 筛选Top N候选人
            min_score: 最低评分阈值
            max_pages: 最大抓取页数

        Returns:
            流水线执行结果
        """
        # 尝试使用 DAG Pipeline
        try:
            pipeline = create_default_pipeline(config=self.config, on_log=self._log)
            result = pipeline.run(search_config=search_config)
            # 修补 steps (使用 Orchestrator 的 step 列表)
            result.steps = self.steps
            # 同步状态
            for step in result.steps:
                for pstep in self.steps:
                    if pstep.name == step.name:
                        pstep.status = step.status
                        pstep.message = step.message
                        pstep.duration_ms = step.duration_ms

            # 持久化结果
            self._persist_result(result, search_config)
            return result
        except Exception as e:
            self._log(f"⚠️ DAG Pipeline 执行异常，回退到手动模式: {e}")
            return self._run_manual(search_config, top_n, min_score, max_pages)

    def _run_manual(
        self,
        search_config: SearchConfig,
        top_n: int,
        min_score: float,
        max_pages: int,
    ) -> PipelineResult:
        """手动步骤执行 (回退模式)"""
        result = PipelineResult(steps=self.steps)
        self._log("=" * 50)
        self._log("🚀 Cassiel Agent 流水线启动 (手动模式)")
        self._log(f"搜索条件: {search_config.keyword} @ {search_config.city}")
        self._log("=" * 50)

        # ── Step 1: 搜索 ──
        step = self.steps[0]
        step.status = "running"
        self._log(f"\n📌 Step 1: {step.name}")
        try:
            candidates = self._step_search(search_config, max_pages)
            result.candidates = candidates
            step.status = "completed"
            step.message = f"找到 {candidates.total_count} 位候选人"
            self._log(f"✅ {step.message}")
        except Exception as e:
            step.status = "failed"
            step.message = str(e)
            self._log(f"❌ 搜索失败: {e}")
            return result

        # ── Step 2: 评估筛选 ──
        step = self.steps[1]
        step.status = "running"
        self._log(f"\n📌 Step 2: {step.name}")
        try:
            scored = self._step_evaluate(result.candidates, search_config)
            result.candidates = scored
            step.status = "completed"
            step.message = f"评估完成，Top {top_n} 已筛选"
            self._log(f"✅ {step.message}")
        except Exception as e:
            step.status = "failed"
            step.message = str(e)
            self._log(f"❌ 评估失败: {e}")
            return result

        # ── Step 3: 生成邀约 ──
        step = self.steps[2]
        step.status = "running"
        self._log(f"\n📌 Step 3: {step.name}")
        try:
            top_candidates = result.candidates.top_n(top_n)
            invitations = self._step_write(top_candidates, search_config)
            result.invitations = invitations
            step.status = "completed"
            step.message = f"已生成 {len(invitations)} 条邀约文案"
            self._log(f"✅ {step.message}")
        except Exception as e:
            step.status = "failed"
            step.message = str(e)
            self._log(f"❌ 文案生成失败: {e}")

        self._persist_result(result, search_config)
        self._log("\n" + "=" * 50)
        self._log("🏁 流水线执行完成")
        self._log("=" * 50)
        return result

    def _persist_result(self, result: PipelineResult, search_config: SearchConfig) -> None:
        """持久化流水线结果到 SessionStore"""
        try:
            with SessionStore() as store:
                search_id = store.save_search(
                    keyword=search_config.keyword,
                    city=search_config.city,
                    city_code=search_config.get_city_code(),
                    result_count=result.candidates.total_count,
                )
                store.save_candidates(search_id, result.candidates)
                result.search_id = search_id
        except Exception as e:
            self._log(f"⚠️ 保存结果失败: {e}")

    # ── 步骤实现 ──────────────────────────────────────────────

    def _step_search(self, config: SearchConfig, max_pages: int) -> CandidateList:
        """Step 1: 搜索候选人"""
        with BossCollector(on_log=self._log) as collector:
            return collector.search(config=config)

    def _step_evaluate(self, candidates: CandidateList, config: SearchConfig) -> CandidateList:
        """Step 2: 评估筛选"""
        provider = self._get_provider(self.config.model.evaluate_provider)
        evaluator = CandidateFilter(provider=provider)
        return evaluator.evaluate(candidates, config)

    def _step_write(self, candidates: list[Candidate], config: SearchConfig) -> dict[str, str]:
        """Step 3: 生成邀约文案"""
        provider = self._get_provider(self.config.model.write_provider)
        writer = InvitationWriter(provider=provider)
        return writer.generate_batch(candidates, config)
