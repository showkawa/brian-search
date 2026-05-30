"""邀约文案预览组件 — Step 4 UI组件

基于 spike_04_nicegui.py 的预览模式，集成 Phase 1 InvitationWriter:
- ui.select: 选择候选人
- ui.markdown: 渲染邀约文案
- ui.button: 确认发送 / 跳过 / 编辑 / 重新生成
- 确认对话框: 发送前二次确认 (遵守 G-09)
- 状态追踪: 每条文案独立状态 (待发送/已发送/已跳过)

退出条件: 所有候选人已处理 (发送或跳过)
"""

from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from cassiel.models.candidate import Candidate

# ── 默认邀约模板 (占位，实际由 InvitationWriter 生成) ────────

INVITATION_TEMPLATE = """## 🤝 沟通邀约

**{name}** 您好！

我们在 BOSS 直聘上看到您的简历，对您的背景非常感兴趣。

### 职位信息
- **职位**: {title}
- **薪资范围**: {salary}

### 我们看重的点
- {experience} 的丰富经验
- {education} 学历背景
- 综合匹配度 **{score}分**

期待与您进一步沟通！
"""

# ── 状态枚举 ──────────────────────────────────────────────

class InvitationStatus:
    """邀约发送状态"""
    PENDING = "pending"    # 待处理
    SENT = "sent"          # 已发送
    SKIPPED = "skipped"    # 已跳过


class InvitationPreviewComponent:
    """邀约文案预览组件

    管理单个或多个候选人的邀约预览与发送流程。

    特性:
    - 候选人下拉切换
    - Markdown 实时预览
    - 发送前二次确认 (G-09)
    - 编辑模式修改文案
    - 逐条状态追踪

    Usage:
        preview = InvitationPreviewComponent(
            candidates=candidates,
            content_map={"张三": "..."},   # 预生成的文案
            on_regenerate=regenerate_fn,   # 重新生成回调
            on_send=send_fn,               # 发送回调
            on_skip=skip_fn,               # 跳过回调
        )
    """

    def __init__(
        self,
        candidates: list[Candidate] | None = None,
        content_map: dict[str, str] | None = None,
        on_regenerate: Callable[[Candidate], str] | None = None,
        on_send: Callable[[Candidate, str], None] | None = None,
        on_skip: Callable[[Candidate], None] | None = None,
    ) -> None:
        self._candidates = candidates or []
        self._content_map: dict[str, str] = content_map or {}  # name → invitation text
        self._status: dict[str, str] = {}  # name → InvitationStatus

        # 外部回调
        self._on_regenerate = on_regenerate
        self._on_send = on_send
        self._on_skip = on_skip

        self._build_component()

    def _get_name(self, candidate: Candidate, idx: int = 0) -> str:
        """获取候选人显示名"""
        return candidate.name or f"候选人_{idx + 1}"

    def _build_component(self) -> None:
        """构建预览组件"""
        names = [self._get_name(c, i) for i, c in enumerate(self._candidates)] or ["暂无候选人"]

        # ── 候选人选择 + 状态标签 ──
        with ui.row().classes("w-full items-center q-mb-md"):
            self.candidate_select = ui.select(
                label="选择候选人",
                options=names,
                value=names[0],
                on_change=self._on_candidate_changed,
            ).classes("w-64").props("outlined dense")

            self._status_badge = ui.label("").classes("text-caption q-ml-sm")

        # ── 预览区域 ──
        default_candidate = self._candidates[0] if self._candidates else None
        default_name = names[0] if names else ""
        default_content = (
            self._content_map.get(default_name)
            or self._render_template(default_candidate)
            if default_candidate
            else "暂无候选人数据"
        )

        self.md_preview = ui.markdown(default_content).classes(
            "w-full q-pa-md bg-grey-1 rounded-lg"
        )

        # ── 操作按钮行 ──
        with ui.row().classes("w-full q-mt-md gap-2"):
            self._btn_send = ui.button(
                "发送邀约",
                icon="send",
                color="positive",
                on_click=self._on_confirm_send,
            )
            self._btn_skip = ui.button(
                "跳过此候选人",
                icon="skip_next",
                color="warning",
                on_click=self._on_confirm_skip,
            ).props("outline")
            ui.space()
            self._btn_edit = ui.button(
                "编辑文案",
                icon="edit",
                on_click=self._on_edit,
            ).props("flat")
            self._btn_regenerate = ui.button(
                "重新生成",
                icon="refresh",
                on_click=self._on_regenerate_click,
            ).props("flat")

        # ── 编辑弹窗 (隐藏) ──
        self._edit_dialog = ui.dialog()
        with self._edit_dialog, ui.card().classes("w-[600px]"):
            ui.label("编辑邀约文案").classes("text-h6 q-mb-md")
            self._edit_textarea = ui.textarea(
                label="文案内容 (支持 Markdown)",
                value="",
            ).classes("w-full h-64")
            with ui.row().classes("w-full justify-end q-mt-md"):
                ui.button("取消", on_click=self._edit_dialog.close).props("flat")
                ui.button(
                    "保存",
                    color="primary",
                    on_click=self._on_save_edit,
                )

        # ── 确认发送弹窗 (隐藏) ──
        self._confirm_send_dialog = ui.dialog()
        with self._confirm_send_dialog, ui.card().classes("w-96"):
            ui.label("确认发送邀约").classes("text-h6 q-mb-md")
            self._confirm_label = ui.label("").classes("text-body1 q-mb-md")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("取消", on_click=self._confirm_send_dialog.close).props("flat")
                ui.button("确认发送", color="positive", on_click=self._do_send)

        # ── 确认跳过弹窗 (隐藏) ──
        self._confirm_skip_dialog = ui.dialog()
        with self._confirm_skip_dialog, ui.card().classes("w-96"):
            ui.label("确认跳过").classes("text-h6 q-mb-md")
            self._confirm_skip_label = ui.label("").classes("text-body1 q-mb-md")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("取消", on_click=self._confirm_skip_dialog.close).props("flat")
                ui.button("确认跳过", color="warning", on_click=self._do_skip)

        # 初始状态刷新
        self._refresh_status()

    # ── 文案渲染 ──────────────────────────────────────────────

    @staticmethod
    def _render_template(candidate: Candidate | None) -> str:
        """使用内置模板渲染邀约文案"""
        if not candidate:
            return "暂无候选人数据"
        return INVITATION_TEMPLATE.format(
            name=candidate.name or "候选人",
            title=candidate.title or "N/A",
            salary=candidate.salary or "N/A",
            experience=candidate.experience or "N/A",
            education=candidate.education or "N/A",
            score=candidate.score if candidate.score is not None else "N/A",
        )

    def _get_current_content(self) -> str:
        """获取当前候选人的邀约文案"""
        name = self.candidate_select.value
        return self._content_map.get(name, "") or "暂无文案"

    def _get_current_candidate(self) -> Candidate | None:
        """获取当前选中的候选人对象"""
        name = self.candidate_select.value
        return next(
            (c for c in self._candidates if self._get_name(c, i) == name),
            None,
        )

    # ── 候选人切换 ──────────────────────────────────────────────

    def _on_candidate_changed(self) -> None:
        """候选人选择变更回调"""
        name = self.candidate_select.value
        candidate = next(
            (c for c in self._candidates if self._get_name(c, i) == name),
            None,
        )
        if candidate:
            content = self._content_map.get(name) or self._render_template(candidate)
            self.md_preview.content = content
        self._refresh_status()

    # ── 状态管理 ──────────────────────────────────────────────

    def _refresh_status(self) -> None:
        """刷新按钮状态和状态标签"""
        name = self.candidate_select.value
        status = self._status.get(name, InvitationStatus.PENDING)

        # 状态标签
        if status == InvitationStatus.SENT:
            self._status_badge.text = "✅ 已发送"
            self._status_badge.classes("text-positive text-caption q-ml-sm")
        elif status == InvitationStatus.SKIPPED:
            self._status_badge.text = "⏭ 已跳过"
            self._status_badge.classes("text-warning text-caption q-ml-sm")
        else:
            self._status_badge.text = "⏳ 待处理"
            self._status_badge.classes("text-grey-6 text-caption q-ml-sm")

        # 按钮状态
        is_done = status != InvitationStatus.PENDING
        self._btn_send.set_enabled(not is_done)
        self._btn_skip.set_enabled(not is_done)
        self._btn_edit.set_enabled(not is_done)
        self._btn_regenerate.set_enabled(not is_done)

        # 检查全部完成
        if self._all_done():
            ui.notify("所有候选人已处理完毕！", type="positive")

    def _all_done(self) -> bool:
        """是否所有候选人都已处理"""
        if not self._candidates:
            return True
        return all(
            self._status.get(self._get_name(c, i), InvitationStatus.PENDING) != InvitationStatus.PENDING
            for i, c in enumerate(self._candidates)
        )

    def _advance_to_next(self) -> None:
        """跳到下一个待处理的候选人"""
        names = [self._get_name(c, i) for i, c in enumerate(self._candidates)]
        current = self.candidate_select.value
        # 找到当前索引，向后查找第一个待处理的
        try:
            idx = names.index(current)
        except ValueError:
            idx = -1
        for i in range(idx + 1, len(names)):
            name = names[i]
            if self._status.get(name, InvitationStatus.PENDING) == InvitationStatus.PENDING:
                self.candidate_select.value = name
                self._on_candidate_changed()
                return
        # 如果后面没了，从开头找
        for i in range(len(names)):
            name = names[i]
            if self._status.get(name, InvitationStatus.PENDING) == InvitationStatus.PENDING:
                self.candidate_select.value = name
                self._on_candidate_changed()
                return

    # ── 发送逻辑 ──────────────────────────────────────────────

    def _on_confirm_send(self) -> None:
        """点击发送按钮 → 弹出确认框"""
        name = self.candidate_select.value
        candidate = self._get_current_candidate()
        if not candidate:
            ui.notify("请先选择候选人", type="warning")
            return
        self._confirm_label.text = f"确认向 {name} 发送邀约？\n\n职位: {candidate.title or 'N/A'}"
        self._confirm_send_dialog.open()

    def _do_send(self) -> None:
        """确认发送"""
        name = self.candidate_select.value
        content = self._get_current_content()
        candidate = self._get_current_candidate()

        self._status[name] = InvitationStatus.SENT
        self._confirm_send_dialog.close()

        if candidate and self._on_send:
            try:
                self._on_send(candidate, content)
            except Exception as e:
                ui.notify(f"发送失败: {e}", type="negative")
                self._status[name] = InvitationStatus.PENDING
                return

        ui.notify(f"✅ 邀约已发送给 {name}！", type="positive")
        self._refresh_status()
        self._advance_to_next()

    # ── 跳过逻辑 ──────────────────────────────────────────────

    def _on_confirm_skip(self) -> None:
        """点击跳过按钮 → 弹出确认框"""
        name = self.candidate_select.value
        self._confirm_skip_label.text = f"确认跳过 {name}？\n\n该候选人将被标记为「已跳过」。"
        self._confirm_skip_dialog.open()

    def _do_skip(self) -> None:
        """确认跳过"""
        name = self.candidate_select.value
        candidate = self._get_current_candidate()

        self._status[name] = InvitationStatus.SKIPPED
        self._confirm_skip_dialog.close()

        if candidate and self._on_skip:
            try:
                self._on_skip(candidate)
            except Exception as e:
                ui.notify(f"操作失败: {e}", type="negative")
                return

        ui.notify(f"已跳过 {name}", type="warning")
        self._refresh_status()
        self._advance_to_next()

    # ── 编辑逻辑 ──────────────────────────────────────────────

    def _on_edit(self) -> None:
        """打开编辑弹窗"""
        name = self.candidate_select.value
        content = self._content_map.get(name) or self._render_template(self._get_current_candidate())
        self._edit_textarea.value = content
        self._edit_dialog.open()

    def _on_save_edit(self) -> None:
        """保存编辑后的文案"""
        name = self.candidate_select.value
        new_content = self._edit_textarea.value
        self._content_map[name] = new_content
        self.md_preview.content = new_content
        self._edit_dialog.close()
        ui.notify("文案已更新", type="positive")

    # ── 重新生成逻辑 ──────────────────────────────────────────────

    def _on_regenerate_click(self) -> None:
        """重新生成文案"""
        name = self.candidate_select.value
        candidate = self._get_current_candidate()
        if not candidate:
            ui.notify("请先选择候选人", type="warning")
            return

        if self._on_regenerate:
            ui.notify(f"正在为 {name} 重新生成文案...", type="info")
            try:
                new_content = self._on_regenerate(candidate)
                self._content_map[name] = new_content
                self.md_preview.content = new_content
                ui.notify(f"文案已重新生成", type="positive")
            except Exception as e:
                ui.notify(f"重新生成失败: {e}", type="negative")
        else:
            ui.notify("重新生成功能未配置回调", type="warning")

    # ── 公开方法 ──────────────────────────────────────────────

    def get_selected_name(self) -> str:
        """获取当前选中的候选人姓名"""
        return self.candidate_select.value or ""

    def update_content(self, content: str) -> None:
        """更新当前预览内容"""
        self.md_preview.content = content
        name = self.candidate_select.value
        self._content_map[name] = content

    def update_candidates(self, candidates: list[Candidate]) -> None:
        """更新候选人列表 (保留已有的 content 和 status)"""
        old_names = {self._get_name(c, i) for i, c in enumerate(self._candidates)}
        self._candidates = candidates
        names = [self._get_name(c, i) for i, c in enumerate(candidates)]

        # 清理不存在候选人的状态
        new_names = set(names)
        self._content_map = {k: v for k, v in self._content_map.items() if k in new_names}
        self._status = {k: v for k, v in self._status.items() if k in new_names}

        self.candidate_select.options = names
        if names:
            self.candidate_select.value = names[0]
            self._on_candidate_changed()
        else:
            self.md_preview.content = "暂无候选人数据"

    def update_content_map(self, content_map: dict[str, str]) -> None:
        """批量更新邀约文案

        Args:
            content_map: {候选人姓名: 邀约文案}
        """
        self._content_map.update(content_map)
        self._on_candidate_changed()

    def get_status_summary(self) -> dict[str, int]:
        """获取发送状态统计

        Returns:
            {"pending": N, "sent": N, "skipped": N}
        """
        summary = {"pending": 0, "sent": 0, "skipped": 0}
        for status in self._status.values():
            summary[status] = summary.get(status, 0) + 1
        if self._candidates:
            summary["pending"] = len(self._candidates) - summary["sent"] - summary["skipped"]
        return summary
