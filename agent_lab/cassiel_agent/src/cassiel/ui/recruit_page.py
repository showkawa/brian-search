"""招聘Agent页面 — 4步Stepper工作流

包含完整招聘流程的UI和逻辑:
- 搜索条件设置 → 自动搜索 → AI筛选 → 邀约文案生成

从 CassielApp 中提取的独立页面组件。
"""

from __future__ import annotations

import asyncio
import os
import traceback
from typing import Any

from nicegui import ui

from cassiel.config.settings import AppConfig, SearchConfig
from cassiel.evaluator.filter import CandidateFilter
from cassiel.llm.providers import LLMProvider, create_provider
from cassiel.models.candidate import Candidate, CandidateList
from cassiel.session.store import SessionStore
from cassiel.writer.invitation import InvitationWriter
from cassiel.ui.candidate_table import CandidateTableComponent
from cassiel.ui.invitation_preview import InvitationPreviewComponent
from cassiel.ui.model_options import (
    get_available_model_labels, get_missing_providers, get_provider_for_model,
    get_available_providers,
)
from cassiel.ui.search_form import SearchFormComponent


# ═══════════════════════════════════════════════════════════════
# 模拟候选人数据 (跳过搜索时使用)
# ═══════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════
# RecruitPage
# ═══════════════════════════════════════════════════════════════

class RecruitPage:
    """招聘Agent页面

    管理完整的招聘工作流: 搜索条件 → 自动搜索 → AI筛选 → 邀约邮箱预览。
    集成所有 Phase 1 后端模块。

    Usage:
        page = RecruitPage(config=app_config)
        ui.run(...)
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

    def _get_provider_for_step(self, model_id: str) -> LLMProvider:
        """根据模型选择获取或创建 LLM 提供商"""
        provider_name = get_provider_for_model(self.config, model_id)
        api_keys = self.config.api_keys
        api_key = {
            "glm": api_keys.glm_key,
            "qwen": api_keys.qwen_key,
            "deepseek": api_keys.deepseek_key,
        }.get(provider_name, "")
        return create_provider(provider_name, api_key=api_key, model_name=model_id)

    # ═══════════════════════════════════════════════════════════
    # 主页面构建
    # ═══════════════════════════════════════════════════════════

    def build(self) -> None:
        """构建主页面 — 4 步 Stepper 工作流"""
        # ── API 状态检查 ──
        available = get_available_providers(self.config)
        self._is_any_key_configured = bool(available)

        if not available:
            with ui.card().classes("w-full q-mb-md bg-orange-1"):
                with ui.row().classes("items-center w-full"):
                    ui.icon("warning").classes("text-orange q-mr-sm")
                    ui.label("尚未配置任何大模型 API Key，请先在 账户配置 中设置").classes("text-body1 text-orange-8")
                    ui.space()
                    ui.label("前往左侧菜单「⚙️ 账户配置」进行设置").classes("text-caption text-grey-6")

        ui.label("📋 招聘Agent").classes("text-h5 q-mb-md")

        # ── BOSS 直聘登录栏 ──
        self._boss_logged_in = False
        self._boss_client = None

        with ui.card().classes("w-full q-mb-md") as self._boss_card:
            with ui.row().classes("w-full items-center gap-4"):
                self._boss_status_icon = ui.icon("").classes("text-grey-6")
                self._boss_status_label = ui.label("").classes("text-body2")
                self._boss_source_label = ui.label("").classes("text-caption text-grey-6")
                ui.space()
                self._boss_extract_btn = ui.button(
                    "🔐 从浏览器提取",
                    on_click=self._boss_extract_cookies,
                ).props("flat dense color=primary")
                self._boss_refresh_btn = ui.button(
                    "🔄 刷新",
                    on_click=self._boss_extract_cookies,
                ).props("flat dense color=primary")
                self._boss_logout_btn = ui.button(
                    "🚪 退出",
                    on_click=self._boss_logout,
                ).props("flat dense")

        # ── LLM 模型选择栏 ──
        with ui.row().classes("w-full q-mb-md gap-4 items-center"):
            ui.icon("settings").classes("text-grey-6")

            available_labels = get_available_model_labels(self.config)
            missing = get_missing_providers(self.config)

            if not available_labels:
                with ui.row().classes("items-center"):
                    ui.icon("warning").classes("text-orange q-mr-sm")
                    ui.label(
                        "暂无可用模型，请先在左侧「⚙️ 账户配置」中测试连接并启用模型"
                    ).classes("text-body1 text-orange-8")
            else:
                search_default = self.config.model.search_model or ""
                eval_default = self.config.model.evaluate_model or ""
                write_default = self.config.model.write_model or ""

                search_model_select = ui.select(
                    label="搜索/采集模型",
                    options=available_labels,
                    value=search_default if search_default in available_labels else (available_labels[0] if available_labels else ""),
                ).classes("w-64").props("outlined dense")

                eval_model_select = ui.select(
                    label="评估/筛选模型",
                    options=available_labels,
                    value=eval_default if eval_default in available_labels else (available_labels[0] if available_labels else ""),
                ).classes("w-64").props("outlined dense")

                write_model_select = ui.select(
                    label="文案生成模型",
                    options=available_labels,
                    value=write_default if write_default in available_labels else (available_labels[0] if available_labels else ""),
                ).classes("w-64").props("outlined dense")

            # 未配置的提供商提示
            if missing:
                missing_text = "、".join(missing)
                ui.label(f"未配置: {missing_text}，前往 账户配置").classes("text-caption text-orange-6")

        # ═══════════════════════════════════════════════════════
        # Stepper 工作流（需登录后可见）
        # ═══════════════════════════════════════════════════════

        self._stepper_container = ui.element('div').classes('w-full')

        with self._stepper_container:
            with ui.stepper().classes('w-full') as stepper:
                with ui.step('设置条件'):
                    search_form = SearchFormComponent(self.config.search)
                    with ui.row().classes('q-mt-md gap-2'):
                        ui.button('下一步', icon='arrow_forward',
                            on_click=lambda: self._on_step1_next(search_form, stepper))
                        ui.button('重置', icon='restart_alt',
                            on_click=lambda: search_form.reset()).props('flat')

                with ui.step('自动搜索'):
                    ui.label('正在搜索候选人...').classes('text-h6')
                    search_log = ui.log(max_lines=30).classes('w-full h-48')
                    search_progress = ui.linear_progress(value=0).classes('w-full q-mt-sm')
                    with ui.row().classes('q-mt-md gap-2'):
                        ui.button('开始搜索', icon='search',
                            on_click=lambda: self._start_search(search_form, search_log, search_progress, stepper))
                        ui.button('跳过 (使用模拟数据)', icon='skip_next',
                            on_click=lambda: self._skip_search(search_log, stepper)).props('flat')

                with ui.step('AI 筛选'):
                    ui.label('候选人筛选结果').classes('text-h6')
                    table = CandidateTableComponent(self._candidates)
                    selected_label = ui.label('请点击表格行查看候选人详情').classes('text-subtitle2 text-grey-6 q-mt-md')
                    def on_row_clicked(e: Any) -> None:
                        row_data = e.args.get('data')
                        if not row_data: return
                        candidate = table.mark_selected(row_data)
                        selected_label.text = f"已选择: {row_data.get('name', '')} — {row_data.get('title', '')} ({row_data.get('score', 'N/A')}分)"
                        if candidate: table.show_detail_dialog(candidate)
                    table.grid.on('rowClicked', on_row_clicked)
                    with ui.row().classes('q-mt-md gap-2'):
                        ui.button('运行 AI 筛选', icon='psychology',
                            on_click=lambda: self._run_evaluation(search_form, eval_model_select, table, stepper))
                        ui.button('下一步：生成邀约', icon='arrow_forward', on_click=stepper.next)
                        ui.button('上一步', icon='arrow_back', on_click=stepper.previous).props('flat')

                with ui.step('生成邀约'):
                    ui.label('邀约文案预览').classes('text-h6')
                    preview = InvitationPreviewComponent(
                        candidates=self._candidates.candidates, content_map={},
                        on_regenerate=lambda c: self._regenerate_single(c, search_form, write_model_select),
                        on_send=lambda c, t: self._handle_send(c, t),
                        on_skip=lambda c: self._handle_skip(c))
                    with ui.row().classes('q-mt-md gap-2'):
                        ui.button('生成全部邀约', icon='auto_awesome',
                            on_click=lambda: self._generate_all_invitations(search_form, write_model_select, preview, stepper))
                        ui.button('上一步', icon='arrow_back', on_click=stepper.previous).props('flat')

        self._sync_boss_ui()

    # ═══════════════════════════════════════════════════════════
    # BOSS 登录
    # ═══════════════════════════════════════════════════════════

    def _sync_boss_ui(self) -> None:
        from cassiel.collector.boss_client import BossApiClient, COOKIES_FILE

        if self._boss_logged_in and self._boss_client:
            source_name = getattr(self, "_boss_source", "浏览器")
            self._boss_status_icon.name = "check_circle"
            self._boss_status_icon.classes("text-positive")
            self._boss_status_label.set_text("✓ 已登录")
            self._boss_status_label.classes("text-body2 text-positive")
            self._boss_source_label.set_text(f"来源: {source_name}")
            self._boss_extract_btn.set_visibility(False)
            self._boss_refresh_btn.set_visibility(True)
            self._boss_logout_btn.set_visibility(True)
        elif COOKIES_FILE.exists():
            self._boss_status_icon.name = "warning"
            self._boss_status_icon.classes("text-orange")
            self._boss_status_label.set_text("⚠ 请先登录")
            self._boss_status_label.classes("text-body2 text-orange")
            self._boss_source_label.set_text("")
            self._boss_extract_btn.set_visibility(True)
            self._boss_refresh_btn.set_visibility(False)
            self._boss_logout_btn.set_visibility(False)
        else:
            self._boss_status_icon.name = "info"
            self._boss_status_icon.classes("text-grey-6")
            self._boss_status_label.set_text("请登录 BOSS 直聘后使用")
            self._boss_status_label.classes("text-body2 text-grey-6")
            self._boss_source_label.set_text("")
            self._boss_extract_btn.set_visibility(True)
            self._boss_refresh_btn.set_visibility(False)
            self._boss_logout_btn.set_visibility(False)

        self._sync_stepper_visibility()

    def _sync_stepper_visibility(self) -> None:
        if self._boss_logged_in:
            self._stepper_container.set_visibility(True)
        else:
            self._stepper_container.set_visibility(False)

    async def _boss_extract_cookies(self) -> None:
        from cassiel.collector.boss_client import BossApiClient

        self._boss_status_label.set_text("⏳ 正在从 Chrome/Edge 提取...")
        self._boss_status_label.classes("text-body2 text-orange")
        self._boss_extract_btn.disable()

        try:
            def _extract() -> dict[str, str] | None:
                return BossApiClient.extract_from_browser()

            loop = asyncio.get_running_loop()
            cookies = await loop.run_in_executor(None, _extract)

            if cookies:
                client = BossApiClient(cookies=cookies)
                client.save_cookies()
                self._boss_client = client
                self._boss_logged_in = True
                self._boss_source = "浏览器"
                self._sync_boss_ui()
                ui.notify(f"登录成功！已提取 {len(cookies)} 个 Cookie", type="positive")
            else:
                self._sync_boss_ui()
                ui.notify("未找到 BOSS 直聘 Cookie\n\n请确认:\n1. 已在 Chrome/Edge 中登录过 boss.zhipin.com\n2. 关闭浏览器后重试（浏览器运行时可能锁库）", type="warning", timeout=10000)
        except Exception as e:
            self._sync_boss_ui()
            err = str(e)
            if "lock" in err.lower() or "database" in err.lower():
                msg = "Cookie 数据库被锁定\n请关闭所有 Chrome/Edge 窗口后重试"
            elif "permission" in err.lower() or "access" in err.lower():
                msg = f"无法访问浏览器 Cookie\n{err}"
            else:
                msg = f"提取失败: {err}"
            ui.notify(msg, type="negative", timeout=10000)
        finally:
            self._boss_extract_btn.enable()

    def _boss_logout(self) -> None:
        from cassiel.collector.boss_client import BossApiClient, COOKIES_FILE

        if self._boss_client:
            self._boss_client.close()
        self._boss_client = None
        self._boss_logged_in = False
        try:
            COOKIES_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        self._sync_boss_ui()
        ui.notify("已退出 BOSS 直聘登录", type="info")

    # ═══════════════════════════════════════════════════════════
    # Step 1 回调
    # ═══════════════════════════════════════════════════════════

    def _on_step1_next(
        self,
        search_form: SearchFormComponent,
        stepper: Any) -> None:
        """Step 1 → 验证表单 → 保存配置 → 进入 Step 2"""
        errors = search_form.validate()
        if errors:
            for err in errors:
                ui.notify(f"⚠️ {err}", type="warning")
            return

        config = search_form.get_config()
        self.config.search = config
        ui.notify(f"条件已设置: {config.keyword} @ {config.city}", type="positive")
        stepper.next()

    # ═══════════════════════════════════════════════════════════
    # Step 2 回调 — 真实搜索 & 模拟跳过
    # ═══════════════════════════════════════════════════════════

    def _start_search(
        self,
        search_form: SearchFormComponent,
        search_log: ui.log,
        search_progress: ui.linear_progress,
        stepper: Any) -> None:
        config = search_form.get_config()
        search_log.push("▶ 开始搜索...")
        search_progress.value = 0

        if not self._boss_client:
            ui.notify("请先登录 BOSS 直聘", type="warning")
            return

        client = self._boss_client

        async def _run_search() -> None:
            try:
                search_log.push(f"🔍 搜索: {config.keyword} @ {config.city}")
                data = client.search_candidates(
                    keyword=config.keyword,
                    city=config.city_code or config.get_city_code(),
                )

                if data is None:
                    search_log.push("❌ 搜索失败，请检查网络或重新登录")
                    ui.notify("搜索失败", type="negative")
                    return

                geek_list = data.get("geekList", data.get("resultList", []))
                if not geek_list:
                    search_log.push("⚠ 未找到匹配候选人")
                    ui.notify("未找到匹配候选人", type="warning")
                    return

                candidates = CandidateList(
                    search_keyword=config.keyword,
                    search_city=config.city,
                )
                for geek in geek_list:
                    candidates.add(Candidate(
                        name=geek.get("geekName", geek.get("name", "")),
                        title=geek.get("expectPositionName", geek.get("jobName", "")),
                        salary=str(geek.get("expectSalary", geek.get("salary", ""))),
                        experience=geek.get("workYearDesc", geek.get("workYear", "")),
                        education=geek.get("degreeDesc", geek.get("degree", "")),
                        company="",
                        online_status="",
                        raw_data=geek,
                    ))

                search_progress.value = 1.0
                self._candidates = candidates
                search_log.push(f"✅ 搜索完成！共找到 {candidates.total_count} 位候选人")

                try:
                    with SessionStore() as store:
                        self._search_id = store.save_search(
                            keyword=config.keyword, city=config.city,
                            city_code=config.get_city_code(),
                            result_count=candidates.total_count,
                        )
                        store.save_candidates(self._search_id, candidates)
                except Exception:
                    pass

                ui.notify(f"搜索完成！找到 {candidates.total_count} 位候选人", type="positive")
                stepper.next()

            except Exception as e:
                err_msg = f"搜索失败: {e}"
                search_log.push(f"❌ {err_msg}")
                traceback.print_exc()
                ui.notify(err_msg, type="negative")

        asyncio.ensure_future(_run_search())

    def _skip_search(
        self,
        search_log: ui.log,
        stepper: Any) -> None:
        config = self.config.search

        async def _simulate() -> None:
            steps = [
                "正在连接 BOSS 直聘...",
                "正在获取职位列表...",
                "正在抓取候选人信息...",
                "正在解析简历数据...",
                "搜索完成！共找到 5 位模拟候选人",
            ]
            for msg in steps:
                await asyncio.sleep(0.5)
                search_log.push(msg)
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
        stepper: Any) -> None:
        """运行 LLM 评估筛选

        错误处理: LLM 调用失败时逐个跳过，不中断整体流程
        """
        if not self._candidates.candidates:
            ui.notify("没有候选人数据，请先执行搜索", type="warning")
            return

        config = search_form.get_config()

        # 解析模型选择
        model_id = eval_model_select.value

        async def _evaluate() -> None:
            try:
                pass  # (removed log)
                ui.notify(f"正在评估 {self._candidates.total_count} 位候选人，请稍候...", type="info")

                loop = asyncio.get_running_loop()

                def _do_evaluate() -> CandidateList:
                    provider = self._get_provider_for_step(model_id)
                    evaluator = CandidateFilter(provider=provider)
                    return evaluator.evaluate(self._candidates, config)

                scored = await loop.run_in_executor(None, _do_evaluate)

                self._candidates = scored
                table.update(scored)
                top_score = scored.candidates[0].score if scored.candidates else "N/A"
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
        stepper: Any) -> None:
        """批量生成所有候选人的邀约文案"""
        if not self._candidates.candidates:
            ui.notify("没有候选人数据", type="warning")
            return

        config = search_form.get_config()
        model_id = write_model_select.value

        async def _generate() -> None:
            try:
                count = len(self._candidates.candidates)
                pass  # (removed log)
                ui.notify(f"正在生成 {count} 条邀约文案...", type="info")

                loop = asyncio.get_running_loop()

                def _do_generate() -> dict[str, str]:
                    provider = self._get_provider_for_step(model_id)
                    writer = InvitationWriter(provider=provider)
                    self._cached_writer = writer
                    return writer.generate_batch(self._candidates.candidates, config)

                content_map = await loop.run_in_executor(None, _do_generate)

                preview.update_content_map(content_map)
                pass  # (removed log)
                ui.notify(f"已生成 {len(content_map)} 条邀约文案！", type="positive")

            except Exception as e:
                err_msg = f"文案生成失败: {e}"
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
        write_model_select: ui.select) -> str:
        """为单个候选人重新生成邀约文案 (同步回调，由预览组件触发)"""
        config = search_form.get_config()
        model_id = write_model_select.value

        provider = self._get_provider_for_step(model_id)
        writer = InvitationWriter(provider=provider)
        text = writer.generate(candidate, config)
        return text

    def _handle_send(self, candidate: Candidate, content: str) -> None:
        """处理邀约发送 (回调)"""
        name = candidate.name or "候选人"
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
            pass

    def _handle_skip(self, candidate: Candidate) -> None:
        """处理跳过候选人 (回调)"""
        name = candidate.name or "候选人"
