"""候选人列表组件 — Step 3 UI组件

基于 spike_04_nicegui.py 的 aggrid 模式，集成 Phase 1 CandidateFilter:
- ui.aggrid: 候选人表格展示 (姓名/职位/薪资/经验/学历/公司/评分/理由)
- ui.select: 排序方式切换 (按评分/姓名/薪资)
- 行点击 → 详情弹窗 (含评分理由)
- 单选模式，供 Step 4 使用
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from cassiel.models.candidate import Candidate, CandidateList

# ── 排序方式定义 ──────────────────────────────────────────────

_SORT_OPTIONS: dict[str, str] = {
    "score": "按评分降序",
    "name": "按姓名升序",
    "salary": "按薪资降序",
}

_SORT_DEFAULTS: dict[str, dict[str, str]] = {
    "score": {"column": "score", "order": "desc"},
    "name": {"column": "name", "order": "asc"},
    "salary": {"column": "salary_raw", "order": "desc"},
}


def _parse_salary_to_int(salary: str) -> int:
    """解析薪资字符串为整数 (用于排序)

    "30-40K" → 30,  "25-35K" → 25,  "" → 0
    """
    if not salary:
        return 0
    try:
        parts = salary.replace("K", "").replace("k", "").split("-")
        return int(parts[0].strip())
    except (ValueError, IndexError):
        return 0


class CandidateTableComponent:
    """候选人列表表格组件

    包装 ui.aggrid 实现:
    - 表格展示 + 行单选
    - 排序切换
    - 行详情弹窗
    - 与 CandidateList 无缝集成

    Usage:
        table = CandidateTableComponent(candidates)
        table.grid.on("rowClicked", handler)
        table.update(new_candidates)
        selected = table.get_selected()
    """

    def __init__(self, candidates: CandidateList | None = None) -> None:
        self._candidates = candidates or CandidateList()
        self._selected_row_data: dict[str, Any] | None = None  # 最后一次点击的行数据

        # 排序选择器
        self.sort_select = ui.select(
            label="排序方式",
            options=list(_SORT_OPTIONS.values()),
            value=_SORT_OPTIONS["score"],
            on_change=self._on_sort_changed,
        ).classes("w-48 q-mb-sm").props("outlined dense")

        self.grid = self._build_table()

    # ── 表格构造 ──────────────────────────────────────────────

    def _build_table(self) -> ui.aggrid:
        """构建 aggrid 表格"""
        options = {
            "columnDefs": [
                {"headerName": "姓名", "field": "name", "width": 80, "sortable": True},
                {"headerName": "职位", "field": "title", "width": 160, "sortable": True},
                {"headerName": "薪资", "field": "salary", "width": 100},
                {"headerName": "经验", "field": "experience", "width": 90},
                {"headerName": "学历", "field": "education", "width": 80},
                {"headerName": "公司", "field": "company", "width": 140},
                {"headerName": "评分", "field": "score", "width": 80, "sortable": True},
                {"headerName": "评分理由", "field": "score_reason", "width": 200,
                 "tooltipField": "score_reason"},
            ],
            "rowData": self._to_row_data(sort_by="score"),
            "rowSelection": "single",
            "defaultColDef": {
                "resizable": True,
                "wrapText": True,
                "autoHeight": False,
            },
        }
        return ui.aggrid(options, theme="balham").classes("w-full h-64")

    # ── 数据转换 ──────────────────────────────────────────────

    def _to_row_data(self, sort_by: str = "score") -> list[dict[str, Any]]:
        """将候选人列表转为表格行数据

        Args:
            sort_by: 排序字段 (score / name / salary)
        """
        rows = [
            {
                "name": c.name or f"候选人_{i + 1}",
                "title": c.title or "N/A",
                "salary": c.salary or "N/A",
                "salary_raw": _parse_salary_to_int(c.salary or ""),
                "experience": c.experience or "N/A",
                "education": c.education or "N/A",
                "company": c.company or "N/A",
                "score": c.score if c.score is not None else "-",
                "score_reason": c.score_reason or "",
                "_candidate_index": i,  # 内部索引，用于 get_selected
            }
            for i, c in enumerate(self._candidates.candidates)
        ]

        # 客户端排序
        if sort_by == "score":
            rows.sort(key=lambda r: r["score"] if isinstance(r["score"], (int, float)) else -1, reverse=True)
        elif sort_by == "name":
            rows.sort(key=lambda r: r["name"])
        elif sort_by == "salary":
            rows.sort(key=lambda r: r["salary_raw"], reverse=True)

        return rows

    # ── 排序 ──────────────────────────────────────────────

    def _on_sort_changed(self) -> None:
        """排序方式变更回调"""
        selected_label = self.sort_select.value
        sort_key = next(
            (k for k, v in _SORT_OPTIONS.items() if v == selected_label),
            "score",
        )
        self.grid.options["rowData"] = self._to_row_data(sort_by=sort_key)
        self.grid.update()

    # ── 公开方法 ──────────────────────────────────────────────

    def update(self, candidates: CandidateList) -> None:
        """更新表格数据

        Args:
            candidates: 新的候选人列表
        """
        self._candidates = candidates
        self._selected_row_data = None
        sort_key = next(
            (k for k, v in _SORT_OPTIONS.items() if v == self.sort_select.value),
            "score",
        )
        self.grid.options["rowData"] = self._to_row_data(sort_by=sort_key)
        self.grid.update()

    def get_selected(self) -> Candidate | None:
        """获取选中的候选人

        NOTE: aggrid 的选择需要通过 rowClicked 事件捕获，
              调用方应在 rowClicked 回调中保存选中的候选人信息，
              然后调用本方法获取。

        Returns:
            当前选中的候选人，无选中则返回 None
        """
        if self._selected_row_data is None:
            return None
        idx = self._selected_row_data.get("_candidate_index", -1)
        if 0 <= idx < len(self._candidates.candidates):
            return self._candidates.candidates[idx]
        return None

    def mark_selected(self, row_data: dict[str, Any]) -> Candidate | None:
        """标记行选中 (由外部 rowClicked 回调调用)

        Args:
            row_data: aggrid 行点击事件中的 data

        Returns:
            选中的 Candidate 对象
        """
        self._selected_row_data = row_data
        return self.get_selected()

    def get_candidate_count(self) -> int:
        """获取候选人总数"""
        return self._candidates.total_count

    def get_candidates(self) -> CandidateList:
        """获取当前候选人列表"""
        return self._candidates

    # ── 详情弹窗 ──────────────────────────────────────────────

    def show_detail_dialog(self, candidate: Candidate) -> None:
        """显示候选人详情弹窗

        Args:
            candidate: 要展示详情的候选人
        """
        name = candidate.name or "未知"
        score_display = f"{candidate.score}分" if candidate.score is not None else "未评估"

        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(f"候选人详情 — {name}").classes("text-h6 q-mb-md")

            with ui.list().classes("w-full"):
                ui.item_label(f"职位: {candidate.title or 'N/A'}")
                ui.item_label(f"薪资: {candidate.salary or 'N/A'}")
                ui.item_label(f"经验: {candidate.experience or 'N/A'}")
                ui.item_label(f"学历: {candidate.education or 'N/A'}")
                ui.item_label(f"公司: {candidate.company or 'N/A'}")
                ui.item_label(f"在线状态: {candidate.online_status or 'N/A'}")
                if candidate.profile_url:
                    ui.link("查看 BOSS 直聘主页", candidate.profile_url, new_tab=True)

            ui.separator()

            ui.label(f"匹配度评分: {score_display}").classes("text-subtitle1")
            if candidate.score_reason:
                ui.label("评分理由:").classes("text-caption text-grey-6")
                ui.label(candidate.score_reason).classes("text-body1 q-mt-xs")

            with ui.row().classes("w-full justify-end"):
                ui.button("关闭", on_click=dialog.close).props("flat")

        dialog.open()
