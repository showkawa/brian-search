"""NiceGUI主窗口 — Cassiel Agent桌面应用入口

基于 spike_04_nicegui.py 验证的模式，集成 Phase 1 后端模块:
- BossCollector (真实的 Playwright 搜索)
- CandidateFilter (LLM 评估打分)
- InvitationWriter (LLM 邀约文案生成)
- create_provider (GLM/Qwen/DeepSeek 统一接口)
- SessionStore (搜索历史持久化)

工作流: 搜索条件 → 自动搜索 → AI筛选 → 邀约预览 (4 步 Stepper)
"""

from __future__ import annotations

import asyncio
import os
import traceback
from typing import Any

from nicegui import ui

from cassiel.collector.boss import (
    BossCollector,
    CaptchaError,
    RateLimitError,
    NetworkError,
    LoginExpiredError,
)
from cassiel.config.settings import AppConfig, SearchConfig
from cassiel.evaluator.filter import CandidateFilter
from cassiel.llm.providers import LLMProvider, create_provider
from cassiel.models.candidate import Candidate, CandidateList
from cassiel.session.store import SessionStore
from cassiel.writer.invitation import InvitationWriter
from cassiel.ui.candidate_table import CandidateTableComponent
from cassiel.ui.invitation_preview import InvitationPreviewComponent
from cassiel.ui.search_form import SearchFormComponent

# ═══════════════════════════════════════════════════════════════
# 模型选项 — 格式: "provider:model" → 显示标签
# ═══════════════════════════════════════════════════════════════

_MODEL_OPTIONS: dict[str, str] = {
    # GLM 系列 (智谱)
    "glm:glm-4-flash": "GLM-4 Flash (智谱) — 快速",
    "glm:glm-4-plus": "GLM-4 Plus (智谱) — 均衡",
    "glm:glm-4": "GLM-4 (智谱) — 标准",
    # Qwen 系列 (通义)
    "qwen:qwen-turbo": "Qwen Turbo (通义) — 快速",
    "qwen:qwen-plus": "Qwen Plus (通义) — 均衡",
    "qwen:qwen-max": "Qwen Max (通义) — 高质量",
    # DeepSeek 系列
    "deepseek:deepseek-chat": "DeepSeek Chat — 通用",
    "deepseek:deepseek-coder": "DeepSeek Coder — 代码",
}

def _parse_model_key(model_key: str) -> tuple[str, str]:
    """解析 'provider:model' → ('provider', 'model')"""
    try:
        provider, model = model_key.split(":", 1)
        return provider.strip(), model.strip()
    except ValueError:
        return "glm", "glm-4-flash"


def _model_options_for_provider(provider: str) -> list[str]:
    """获取某提供商的模型选项 (仅显示标签)"""
    return [label for key, label in _MODEL_OPTIONS.items() if key.startswith(f"{provider}:")]

def _all_model_labels() -> list[str]:
    """所有模型标签"""
    return list(_MODEL_OPTIONS.values())


# ═══════════════════════════════════════════════════════════════
# CassielApp 主应用
# ═══════════════════════════════════════════════════════════════

class CassielApp:
    """Cassiel Agent 主应用

    管理 NiceGUI 界面和流水线编排。集成所有 Phase 1 后端模块。

    Usage:
        app = CassielApp()
        app.run()
    """

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or self._load_config()
        self._candidates: CandidateList = CandidateList()
        self._selected_candidate: Candidate | None = None
        self._search_id: int = 0

        # 缓存的 LLM 组件
        self._providers: dict[str, LLMProvider] = {}
        self._cached_writer: InvitationWriter | None = None

        # 初始化 LLM 提供商
        self._init_providers()

    def _load_config(self) -> AppConfig:
        """加载配置 (config.json 或环境变量)"""
        try:
            cfg = AppConfig.from_json()
            # 环境变量覆盖 API Keys
            if not cfg.api_keys.glm_key:
                cfg.api_keys.glm_key = os.getenv("GLM_API_KEY", "")
            if not cfg.api_keys.qwen_key:
                cfg.api_keys.qwen_key = os.getenv("QWEN_API_KEY", "")
            if not cfg.api_keys.deepseek_key:
                cfg.api_keys.deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
            return cfg
        except Exception:
            return AppConfig()

    def _init_providers(self) -> None:
        """初始化所有可用的 LLM 提供商"""
        api_keys = self.config.api_keys
        for name, key in [("glm", api_keys.glm_key), ("qwen", api_keys.qwen_key), ("deepseek", api_keys.deepseek_key)]:
            if key:
                try:
                    self._providers[name] = create_provider(name, api_key=key)
                except Exception:
                    pass

    def _get_provider_for_step(self, model_key: str) -> LLMProvider:
        """根据模型选择获取或创建 LLM 提供商"""
        provider_name, model_name = _parse_model_key(model_key)
        api_keys = self.config.api_keys
        api_key = {
            "glm": api_keys.glm_key,
            "qwen": api_keys.qwen_key,
            "deepseek": api_keys.deepseek_key,
        }.get(provider_name, "")
        return create_provider(provider_name, api_key=api_key, model_name=model_name)

    # ═══════════════════════════════════════════════════════════
    # 主页面
    # ═══════════════════════════════════════════════════════════

    @ui.page("/")
    def main_page(self) -> None:
        """主页面 — 4 步 Stepper 工作流"""
        ui.label("Cassiel Agent — BOSS 直聘智能招聘助手").classes("text-h4 q-mb-md")

        # ── 全局操作日志 ──
        log = ui.log(max_lines=50).classes("w-full h-32 q-mb-md")
        log.push("系统就绪，等待操作...")

        # ── LLM 模型选择栏 ──
        with ui.row().classes("w-full q-mb-md gap-4 items-center"):
            ui.icon("settings").classes("text-grey-6")
            all_labels = _all_model_labels()

            search_default = f"{self.config.model.search_provider}:{self.config.model.search_model}"
            search_default_label = _MODEL_OPTIONS.get(search_default, all_labels[0])

            eval_default = f"{self.config.model.evaluate_provider}:{self.config.model.evaluate_model}"
            eval_default_label = _MODEL_OPTIONS.get(eval_default, all_labels[-1] if all_labels else "")

            write_default = f"{self.config.model.write_provider}:{self.config.model.write_model}"
            write_default_label = _MODEL_OPTIONS.get(write_default, all_labels[0])

            search_model_select = ui.select(
                label="搜索/采集模型",
                options=all_labels,
                value=search_default_label,
            ).classes("w-64").props("outlined dense")

            eval_model_select = ui.select(
                label="评估/筛选模型",
                options=all_labels,
                value=eval_default_label,
            ).classes("w-64").props("outlined dense")

            write_model_select = ui.select(
                label="文案生成模型",
                options=all_labels,
                value=write_default_label,
            ).classes("w-64").props("outlined dense")

        # ═══════════════════════════════════════════════════════
        # Stepper 工作流
        # ═══════════════════════════════════════════════════════

        with ui.stepper().classes("w-full") as stepper:
            # ── Step 1: 设置条件 ──
            with ui.step("设置条件"):
                search_form = SearchFormComponent(self.config.search)

                with ui.row().classes("q-mt-md gap-2"):
                    ui.button(
                        "下一步",
                        icon="arrow_forward",
                        on_click=lambda: self._on_step1_next(search_form, stepper, log),
                    )
                    ui.button(
                        "重置",
                        icon="restart_alt",
                        on_click=lambda: search_form.reset(),
                    ).props("flat")

            # ── Step 2: 自动搜索 ──
            with ui.step("自动搜索"):
                ui.label("正在搜索候选人...").classes("text-h6")

                search_log = ui.log(max_lines=30).classes("w-full h-48")
                search_progress = ui.linear_progress(value=0).classes("w-full q-mt-sm")

                with ui.row().classes("q-mt-md gap-2"):
                    ui.button(
                        "开始搜索",
                        icon="search",
                        on_click=lambda: self._start_search(
                            search_form, search_log, search_progress, stepper, log
                        ),
                    )
                    ui.button(
                        "跳过 (使用模拟数据)",
                        icon="skip_next",
                        on_click=lambda: self._skip_search(search_log, stepper, log),
                    ).props("flat")

            # ── Step 3: AI 筛选 ──
            with ui.step("AI 筛选"):
                ui.label("候选人筛选结果").classes("text-h6")
                table = CandidateTableComponent(self._candidates)

                selected_label = ui.label("请点击表格行查看候选人详情").classes(
                    "text-subtitle2 text-grey-6 q-mt-md"
                )

                # 行点击 → 更新选中 + 显示详情弹窗
                def on_row_clicked(e: Any) -> None:
                    row_data = e.args.get("data")
                    if not row_data:
                        return
                    candidate = table.mark_selected(row_data)
                    name = row_data.get("name", "未知")
                    score = row_data.get("score", "N/A")
                    selected_label.text = f"已选择: {name} — {row_data.get('title', '')} ({score}分)"

                    if candidate:
                        table.show_detail_dialog(candidate)
                        log.push(f"选中候选人: {name} ({score}分)")

                table.grid.on("rowClicked", on_row_clicked)

                with ui.row().classes("q-mt-md gap-2"):
                    ui.button(
                        "运行 AI 筛选",
                        icon="psychology",
                        on_click=lambda: self._run_evaluation(
                            search_form, eval_model_select, table, stepper, log
                        ),
                    )
                    ui.button("下一步：生成邀约", icon="arrow_forward", on_click=stepper.next)
                    ui.button("上一步", icon="arrow_back", on_click=stepper.previous).props("flat")

            # ── Step 4: 生成邀约 ──
            with ui.step("生成邀约"):
                ui.label("邀约文案预览").classes("text-h6")

                preview = InvitationPreviewComponent(
                    candidates=self._candidates.candidates,
                    content_map={},
                    on_regenerate=lambda c: self._regenerate_single(
                        c, search_form, write_model_select, log
                    ),
                    on_send=lambda c, t: self._handle_send(c, t, log),
                    on_skip=lambda c: self._handle_skip(c, log),
                )

                with ui.row().classes("q-mt-md gap-2"):
                    ui.button(
                        "生成全部邀约",
                        icon="auto_awesome",
                        on_click=lambda: self._generate_all_invitations(
                            search_form, write_model_select, preview, stepper, log
                        ),
                    )
                    ui.button("上一步", icon="arrow_back", on_click=stepper.previous).props("flat")

    # ═══════════════════════════════════════════════════════════
    # Step 1 回调
    # ═══════════════════════════════════════════════════════════

    def _on_step1_next(
        self,
        search_form: SearchFormComponent,
        stepper: Any,
        log: ui.log,
    ) -> None:
        """Step 1 → 验证表单 → 保存配置 → 进入 Step 2"""
        errors = search_form.validate()
        if errors:
            for err in errors:
                ui.notify(f"⚠️ {err}", type="warning")
            return

        config = search_form.get_config()
        self.config.search = config
        log.push(f"✅ 搜索条件: 关键词={config.keyword}, 城市={config.city}, "
                 f"薪资={config.salary_min}K-{config.salary_max}K, "
                 f"经验={config.experience}, 学历={config.education}")
        ui.notify(f"条件已设置: {config.keyword} @ {config.city}", type="positive")
        stepper.next()

    # ═══════════════════════════════════════════════════════════
    # Step 2 回调 — 真实搜索 & 模拟跳过
    # ═══════════════════════════════════════════════════════════

    def _start_search(
        self,
        search_form: SearchFormComponent,
        search_log: ui.log,
        progress: ui.linear_progress,
        stepper: Any,
        log: ui.log,
    ) -> None:
        """启动真实搜索 (在后台线程中运行 Playwright)

        错误处理:
        - CaptchaError → 通知用户 + 暂停
        - RateLimitError → 指数退避重试 + 通知
        - NetworkError → 重试提示 + 通知
        """
        config = search_form.get_config()
        search_log.push("▶ 开始搜索...")
        log.push(f"🔍 开始搜索: {config.keyword} @ {config.city}")
        progress.value = 0

        async def _run_search(retry_count: int = 0) -> None:
            """异步包装同步搜索，支持错误恢复"""
            max_retries = 3
            backoff_base = 5.0  # 指数退避基数 (秒)

            try:
                loop = asyncio.get_running_loop()

                def _do_search() -> CandidateList:
                    collector = BossCollector(
                        headless=False,
                        on_log=lambda msg: search_log.push(msg),
                    )
                    try:
                        result = collector.search(config=config)
                        return result
                    finally:
                        collector.close()

                candidates = await loop.run_in_executor(None, _do_search)

                progress.value = 1.0
                self._candidates = candidates
                search_log.push(f"✅ 搜索完成！共找到 {candidates.total_count} 位候选人")
                log.push(f"✅ 搜索完成: {candidates.total_count} 位候选人")

                # 持久化
                try:
                    with SessionStore() as store:
                        self._search_id = store.save_search(
                            keyword=config.keyword,
                            city=config.city,
                            city_code=config.get_city_code(),
                            result_count=candidates.total_count,
                        )
                        store.save_candidates(self._search_id, candidates)
                        log.push(f"💾 搜索结果已保存 (search_id={self._search_id})")
                except Exception as e:
                    log.push(f"⚠️ 保存失败: {e}")

                ui.notify(f"搜索完成！找到 {candidates.total_count} 位候选人", type="positive")
                stepper.next()

            except CaptchaError as e:
                search_log.push(f"🔐 {e}")
                log.push(f"🔐 验证码拦截: {e}")
                ui.notify(
                    "检测到验证码！请在浏览器窗口中手动完成验证后重试",
                    type="warning",
                    timeout=10000,
                )
                progress.value = 0.5

            except RateLimitError as e:
                if retry_count < max_retries:
                    delay = backoff_base * (2 ** retry_count)
                    search_log.push(f"⏱ 频率限制，{delay:.0f}s 后重试 ({retry_count + 1}/{max_retries})...")
                    log.push(f"⏱ 频率限制: {e}，{delay:.0f}s 后重试")
                    ui.notify(
                        f"请求过于频繁，{delay:.0f}秒后自动重试...",
                        type="warning",
                        timeout=int(delay * 1000),
                    )
                    await asyncio.sleep(delay)
                    await _run_search(retry_count + 1)
                else:
                    search_log.push(f"❌ 频率限制重试耗尽")
                    log.push(f"❌ 频率限制重试耗尽: {e}")
                    ui.notify(
                        "请求过于频繁，请手动等待几分钟后重试",
                        type="negative",
                        timeout=8000,
                    )

            except NetworkError as e:
                search_log.push(f"🌐 {e}")
                log.push(f"🌐 网络错误: {e}")
                ui.notify(
                    f"网络连接失败: {e}\n请检查网络后重试",
                    type="negative",
                    timeout=10000,
                )

            except LoginExpiredError as e:
                search_log.push(f"🔑 {e}")
                log.push(f"🔑 登录过期: {e}")
                ui.notify(
                    "登录已过期，请在浏览器窗口中重新登录后重试",
                    type="warning",
                    timeout=10000,
                )

            except Exception as e:
                err_msg = f"搜索失败: {e}"
                search_log.push(f"❌ {err_msg}")
                log.push(f"❌ {err_msg}")
                traceback.print_exc()
                ui.notify(err_msg, type="negative")

        asyncio.ensure_future(_run_search())

    def _skip_search(
        self,
        search_log: ui.log,
        stepper: Any,
        log: ui.log,
    ) -> None:
        """跳过真实搜索，使用模拟数据 (开发/测试用)"""
        config = self.config.search

        async def _simulate() -> None:
            steps = [
                (0.15, "正在连接 BOSS 直聘..."),
                (0.30, "正在获取职位列表..."),
                (0.50, "正在抓取候选人信息..."),
                (0.75, "正在解析简历数据..."),
                (1.0, "搜索完成！共找到 5 位模拟候选人"),
            ]
            for val, msg in steps:
                await asyncio.sleep(0.5)
                search_progress = ui.linear_progress(value=val)
                search_log.push(msg)
                log.push(f"[模拟] {msg}")

            # 填充模拟数据
            self._candidates = CandidateList(
                search_keyword=config.keyword,
                search_city=config.city,
            )
            for i, sample in enumerate(_SIMULATED_CANDIDATES):
                self._candidates.add(Candidate(**sample))

            ui.notify("模拟搜索完成 (5 位候选人)", type="info")
            stepper.next()

        asyncio.ensure_future(_simulate())

    # ═══════════════════════════════════════════════════════════
    # Step 3 回调 — LLM 评估
    # ═══════════════════════════════════════════════════════════

    def _run_evaluation(
        self,
        search_form: SearchFormComponent,
        eval_model_select: ui.select,
        table: CandidateTableComponent,
        stepper: Any,
        log: ui.log,
    ) -> None:
        """运行 LLM 评估筛选

        错误处理: LLM 调用失败时逐个跳过，不中断整体流程
        """
        if not self._candidates.candidates:
            ui.notify("没有候选人数据，请先执行搜索", type="warning")
            return

        config = search_form.get_config()

        # 解析模型选择
        model_label = eval_model_select.value
        model_key = next((k for k, v in _MODEL_OPTIONS.items() if v == model_label), "deepseek:deepseek-chat")

        async def _evaluate() -> None:
            try:
                log.push(f"🤖 开始评估 {self._candidates.total_count} 位候选人 (模型: {model_label})")
                ui.notify(f"正在评估 {self._candidates.total_count} 位候选人，请稍候...", type="info")

                loop = asyncio.get_running_loop()

                def _do_evaluate() -> CandidateList:
                    provider = self._get_provider_for_step(model_key)
                    evaluator = CandidateFilter(provider=provider)
                    return evaluator.evaluate(self._candidates, config)

                scored = await loop.run_in_executor(None, _do_evaluate)

                self._candidates = scored
                table.update(scored)
                top_score = scored.candidates[0].score if scored.candidates else "N/A"
                log.push(f"✅ 评估完成！最高分: {top_score}")

                # 保存评分结果
                if self._search_id:
                    try:
                        with SessionStore() as store:
                            store.save_candidates(self._search_id, scored)
                    except Exception:
                        pass

                ui.notify("评估完成！", type="positive")

            except Exception as e:
                err_msg = f"评估失败: {e}"
                log.push(f"❌ {err_msg}")
                traceback.print_exc()

                # 区分错误类型，给用户更友好的提示
                err_str = str(e).lower()
                if "rate" in err_str or "limit" in err_str or "429" in err_str:
                    ui.notify("LLM 频率限制，请稍后重试", type="warning")
                elif "timeout" in err_str or "connection" in err_str:
                    ui.notify("LLM 连接超时，请检查网络后重试", type="negative")
                elif "auth" in err_str or "key" in err_str or "unauthorized" in err_str:
                    ui.notify("LLM API Key 无效，请检查配置", type="negative")
                else:
                    ui.notify(err_msg, type="negative")

        asyncio.ensure_future(_evaluate())

    # ═══════════════════════════════════════════════════════════
    # Step 4 回调 — 邀约生成 & 操作
    # ═══════════════════════════════════════════════════════════

    def _generate_all_invitations(
        self,
        search_form: SearchFormComponent,
        write_model_select: ui.select,
        preview: InvitationPreviewComponent,
        stepper: Any,
        log: ui.log,
    ) -> None:
        """批量生成所有候选人的邀约文案"""
        if not self._candidates.candidates:
            ui.notify("没有候选人数据", type="warning")
            return

        config = search_form.get_config()
        model_label = write_model_select.value
        model_key = next((k for k, v in _MODEL_OPTIONS.items() if v == model_label), "qwen:qwen-plus")

        async def _generate() -> None:
            try:
                count = len(self._candidates.candidates)
                log.push(f"✍️ 开始生成 {count} 条邀约文案 (模型: {model_label})")
                ui.notify(f"正在生成 {count} 条邀约文案...", type="info")

                loop = asyncio.get_running_loop()

                def _do_generate() -> dict[str, str]:
                    provider = self._get_provider_for_step(model_key)
                    writer = InvitationWriter(provider=provider)
                    self._cached_writer = writer
                    return writer.generate_batch(self._candidates.candidates, config)

                content_map = await loop.run_in_executor(None, _do_generate)

                preview.update_content_map(content_map)
                log.push(f"✅ 已生成 {len(content_map)} 条邀约文案")
                ui.notify(f"已生成 {len(content_map)} 条邀约文案！", type="positive")

            except Exception as e:
                err_msg = f"文案生成失败: {e}"
                log.push(f"❌ {err_msg}")
                traceback.print_exc()

                # 区分错误类型
                err_str = str(e).lower()
                if "rate" in err_str or "limit" in err_str or "429" in err_str:
                    ui.notify("LLM 频率限制，请稍后重试", type="warning")
                elif "timeout" in err_str or "connection" in err_str:
                    ui.notify("LLM 连接超时，请检查网络后重试", type="negative")
                elif "auth" in err_str or "key" in err_str:
                    ui.notify("LLM API Key 无效，请检查配置", type="negative")
                else:
                    ui.notify(err_msg, type="negative")

        asyncio.ensure_future(_generate())

    def _regenerate_single(
        self,
        candidate: Candidate,
        search_form: SearchFormComponent,
        write_model_select: ui.select,
        log: ui.log,
    ) -> str:
        """为单个候选人重新生成邀约文案 (同步回调，由预览组件触发)"""
        config = search_form.get_config()
        model_label = write_model_select.value
        model_key = next((k for k, v in _MODEL_OPTIONS.items() if v == model_label), "qwen:qwen-plus")

        provider = self._get_provider_for_step(model_key)
        writer = InvitationWriter(provider=provider)
        text = writer.generate(candidate, config)
        log.push(f"✍️ 已重新生成: {candidate.name or '候选人'}")
        return text

    def _handle_send(self, candidate: Candidate, content: str, log: ui.log) -> None:
        """处理邀约发送 (回调)"""
        name = candidate.name or "候选人"
        log.push(f"📨 发送邀约给: {name}")
        # v1 阶段仅记录，不实际发送 (遵守 G-09/G-10)
        try:
            with SessionStore() as store:
                # 需要 candidate ID，但这里我们没有 DB ID，记录日志即可
                store.save_invitation(
                    candidate_id=0,
                    content=content,
                    status="sent",
                )
        except Exception as e:
            log.push(f"⚠️ 发送记录保存失败: {e}")

    def _handle_skip(self, candidate: Candidate, log: ui.log) -> None:
        """处理跳过候选人 (回调)"""
        name = candidate.name or "候选人"
        log.push(f"⏭ 跳过候选人: {name}")

    # ═══════════════════════════════════════════════════════════
    # 启动
    # ═══════════════════════════════════════════════════════════

    def run(self, **kwargs: Any) -> None:
        """启动 NiceGUI 应用"""
        self.main_page()
        ui.run(
            native=True,
            title="Cassiel Agent — BOSS 直聘智能招聘助手",
            port=8765,
            **kwargs,
        )


# ═══════════════════════════════════════════════════════════════
# 模拟候选人数据 (跳过搜索时使用)
# ═══════════════════════════════════════════════════════════════

def run(**kwargs: Any) -> None:
    """Module-level entry point for `cassiel-agent` console script."""
    CassielApp().run(**kwargs)


_SIMULATED_CANDIDATES: list[dict[str, Any]] = [
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
