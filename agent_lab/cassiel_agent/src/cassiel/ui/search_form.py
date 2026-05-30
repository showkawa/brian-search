"""搜索条件表单 — Step 1 UI组件

基于 spike_04_nicegui.py 的表单模式，集成 Phase 1 SearchConfig:
- ui.input: 搜索关键词
- ui.select: 城市/经验/学历
- ui.number: 薪资范围、最大页数
- ui.button: 操作按钮
- 表单验证: 薪资范围合法性、必填字段检查
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from cassiel.config.settings import SearchConfig

# ── 下拉选项常量 ──────────────────────────────────────────────

_EXPERIENCE_OPTIONS = ["不限", "1-3年", "3-5年", "5-10年", "10年以上"]
_EDUCATION_OPTIONS = ["不限", "大专", "本科", "硕士", "博士"]

# 从 SearchConfig 默认实例获取城市列表和代码映射
_DEFAULT_SEARCH = SearchConfig()
_CITY_NAMES = list(_DEFAULT_SEARCH.CITY_CODES.keys())


class SearchFormComponent:
    """搜索条件表单组件

    封装 Step 1 的所有表单控件，支持:
    - 从 SearchConfig 初始化
    - get_config() 返回验证后的 SearchConfig
    - reset() 恢复默认值
    - 内置验证: 薪资 min ≤ max, 关键词非空

    Usage:
        form = SearchFormComponent(config)
        config = form.get_config()
    """

    def __init__(self, config: SearchConfig | None = None) -> None:
        self._config = config or SearchConfig()
        self._build_form()

    def _build_form(self) -> None:
        """构建表单布局"""

        ui.label("配置搜索参数").classes("text-h6 q-mb-sm")

        # ── 基本搜索条件 ──
        ui.label("岗位信息").classes("text-subtitle1 q-mt-md q-mb-xs")

        self.keyword_input = ui.input(
            label="搜索关键词",
            placeholder="例如：前端工程师、Python开发",
            value=self._config.keyword,
        ).classes("w-full").props('outlined')

        self.city_select = ui.select(
            label="城市",
            options=_CITY_NAMES,
            value=self._config.city if self._config.city in _CITY_NAMES else _CITY_NAMES[0],
        ).classes("w-full").props('outlined')

        # ── 薪资范围 ──
        ui.label("薪资范围 (K/月)").classes("text-subtitle1 q-mt-md q-mb-xs")

        with ui.row().classes("w-full gap-4"):
            self.salary_min = ui.number(
                label="最低",
                value=self._config.salary_min or 15,
                min=0,
                max=200,
                precision=0,
            ).classes("w-full").props('outlined')
            self.salary_max = ui.number(
                label="最高",
                value=self._config.salary_max or 50,
                min=0,
                max=200,
                precision=0,
            ).classes("w-full").props('outlined')

        # ── 候选人条件 ──
        ui.label("候选人要求").classes("text-subtitle1 q-mt-md q-mb-xs")

        self.experience_select = ui.select(
            label="经验要求",
            options=_EXPERIENCE_OPTIONS,
            value=self._config.experience if self._config.experience in _EXPERIENCE_OPTIONS else _EXPERIENCE_OPTIONS[0],
        ).classes("w-full").props('outlined')

        self.education_select = ui.select(
            label="学历要求",
            options=_EDUCATION_OPTIONS,
            value=self._config.education if self._config.education in _EDUCATION_OPTIONS else _EDUCATION_OPTIONS[0],
        ).classes("w-full").props('outlined')

        # ── 采集设置 ──
        ui.label("采集设置").classes("text-subtitle1 q-mt-md q-mb-xs")

        self.max_pages = ui.number(
            label="最大抓取页数",
            value=self._config.max_pages,
            min=1,
            max=10,
            precision=0,
        ).classes("w-40").props('outlined')

        ui.label(
            "提示: 每页约 15 位候选人，3 页约可抓取 45 位"
        ).classes("text-caption text-grey-6 q-mt-xs")

    # ── 验证 + 导出 ──────────────────────────────────────────

    def validate(self) -> list[str]:
        """验证表单输入

        Returns:
            错误消息列表 (空列表 = 验证通过)
        """
        errors: list[str] = []

        keyword = (self.keyword_input.value or "").strip()
        if not keyword:
            errors.append("搜索关键词不能为空")

        salary_min = int(self.salary_min.value or 0)
        salary_max = int(self.salary_max.value or 0)
        if salary_min > 0 and salary_max > 0 and salary_min > salary_max:
            errors.append("最低薪资不能高于最高薪资")

        max_pages = int(self.max_pages.value or 3)
        if max_pages < 1 or max_pages > 10:
            errors.append("最大抓取页数必须在 1-10 之间")

        return errors

    def get_config(self) -> SearchConfig:
        """获取当前表单的搜索配置

        Returns:
            经过验证的 SearchConfig 对象
        """
        city = self.city_select.value or _CITY_NAMES[0]
        default_cfg = SearchConfig()

        return SearchConfig(
            keyword=(self.keyword_input.value or "").strip(),
            city=city,
            city_code=default_cfg.CITY_CODES.get(city, default_cfg.city_code),
            salary_min=int(self.salary_min.value or 0),
            salary_max=int(self.salary_max.value or 0),
            experience=self.experience_select.value or "不限",
            education=self.education_select.value or "不限",
            max_pages=int(self.max_pages.value or 3),
        )

    def update_from_config(self, config: SearchConfig) -> None:
        """从 SearchConfig 更新表单值"""
        self.keyword_input.value = config.keyword
        self.city_select.value = config.city if config.city in _CITY_NAMES else _CITY_NAMES[0]
        self.salary_min.value = config.salary_min
        self.salary_max.value = config.salary_max
        self.experience_select.value = config.experience if config.experience in _EXPERIENCE_OPTIONS else "不限"
        self.education_select.value = config.education if config.education in _EDUCATION_OPTIONS else "不限"
        self.max_pages.value = config.max_pages

    def reset(self) -> None:
        """重置为默认值"""
        default = SearchConfig()
        self.keyword_input.value = default.keyword
        self.city_select.value = default.city
        self.salary_min.value = default.salary_min or 15
        self.salary_max.value = default.salary_max or 50
        self.experience_select.value = default.experience
        self.education_select.value = default.education
        self.max_pages.value = default.max_pages
        ui.notify("参数已重置为默认值", type="info")
