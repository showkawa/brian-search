"""侧边栏组件 — 品牌标识 + 菜单导航 + 版本号"""

from __future__ import annotations

from nicegui import ui

_VERSION = "v0.1.0"


class Sidebar:
    """应用侧边栏

    固定 200px 宽度，包含:
    - 品牌标识 (✦ Cassiel + 副标题)
    - 菜单项列表 (当前页高亮)
    - 底部版本号

    Args:
        on_navigate: 菜单点击回调，接收页面名称 ("recruit" / "settings")
        active_page: 当前激活页面名称
    """

    # 菜单定义: (页面标识, 图标, 显示文字)
    MENU_ITEMS: list[tuple[str, str, str]] = [
        ("recruit", "📋", "招聘Agent"),
        ("settings", "⚙️", "账户配置"),
    ]

    def __init__(self, on_navigate, active_page: str = "recruit") -> None:
        self._on_navigate = on_navigate
        self._active_page = active_page
        self._menu_buttons: dict[str, ui.button] = {}

    def build(self) -> None:
        """构建侧边栏 UI"""
        with ui.column().classes("w-full h-full q-pa-none q-ma-none"):
            # ── 品牌标识 ──
            with ui.column().classes("q-pa-md q-pb-sm"):
                ui.label("✦ Cassiel").classes("text-h6 text-primary q-mb-none")
                ui.label("HRD 智能助手").classes("text-caption text-grey-6 q-mt-none")

            ui.separator()

            # ── 菜单项 ──
            with ui.column().classes("q-py-sm q-px-none w-full"):
                for page_id, icon, label in self.MENU_ITEMS:
                    is_active = page_id == self._active_page
                    btn_classes = "w-full text-left q-px-md q-py-sm no-border-radius"
                    btn = ui.button(
                        f"{icon}  {label}",
                        on_click=lambda pid=page_id: self._navigate(pid),
                    ).classes(btn_classes)
                    if is_active:
                        btn.classes("bg-blue-1 text-primary", remove="text-grey-7")
                    else:
                        btn.classes("text-grey-7")
                    btn.props("flat no-caps align=left")
                    self._menu_buttons[page_id] = btn

            # ── 底部版本号 ──
            ui.space()
            ui.separator()
            ui.label(_VERSION).classes("text-caption text-grey-5 q-pa-md q-ma-none")

    def _navigate(self, page_id: str) -> None:
        """菜单点击处理"""
        self._active_page = page_id
        self._update_highlight()
        self._on_navigate(page_id)

    def _update_highlight(self) -> None:
        """更新菜单项高亮状态"""
        for page_id, btn in self._menu_buttons.items():
            if page_id == self._active_page:
                btn.classes("bg-blue-1 text-primary", remove="text-grey-7")
            else:
                btn.classes("text-grey-7", remove="bg-blue-1 text-primary")
