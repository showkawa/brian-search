"""Spike 04 — NiceGUI 桌面应用 UI 组件验证

验证 Cassiel Agent 所需的全部 NiceGUI 组件：
- ui.stepper: 工作流步骤
- ui.input / ui.select / ui.number: 搜索参数
- ui.button: 触发操作
- ui.aggrid: 候选人表格
- ui.markdown: 渲染邀约文本
- ui.log: 操作日志
- ui.notify: 提示通知

运行: python brian_agent/cassiel_agent/spikes/spike_04_nicegui.py
"""

import asyncio
from nicegui import ui

# ── 示例数据 ──────────────────────────────────────────────

SAMPLE_CANDIDATES = [
    {"name": "张伟", "title": "高级前端工程师", "salary": "30-40K", "experience": "6年", "education": "本科", "score": 92},
    {"name": "李娜", "title": "全栈开发工程师", "salary": "25-35K", "experience": "4年", "education": "硕士", "score": 88},
    {"name": "王磊", "title": "前端架构师", "salary": "40-55K", "experience": "8年", "education": "本科", "score": 95},
    {"name": "赵敏", "title": "React开发工程师", "salary": "20-30K", "experience": "3年", "education": "本科", "score": 78},
    {"name": "陈晨", "title": "前端技术专家", "salary": "35-50K", "experience": "7年", "education": "硕士", "score": 91},
]

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


# ── 主界面 ──────────────────────────────────────────────

@ui.page("/")
def main():
    ui.label("Cassiel Agent — BOSS直聘智能招聘助手").classes("text-h4 q-mb-md")

    # 操作日志（全局可见）
    log = ui.log(max_lines=50).classes("w-full h-32 q-mb-md")
    log.push("系统就绪，等待操作...")

    # ── Stepper 工作流 ──
    with ui.stepper().classes("w-full") as stepper:
        # ── Step 1: 设置条件 ──
        with ui.step("设置条件"):
            ui.label("配置搜索参数").classes("text-h6")

            keyword_input = ui.input(
                label="搜索关键词",
                placeholder="例如：前端工程师",
                value="前端工程师",
            ).classes("w-full")

            city_select = ui.select(
                label="城市",
                options=["北京", "上海", "深圳", "杭州", "广州", "成都"],
                value="北京",
            ).classes("w-full")

            salary_min = ui.number(label="最低薪资(K)", value=20, min=0, max=200)
            salary_max = ui.number(label="最高薪资(K)", value=50, min=0, max=200)

            experience_select = ui.select(
                label="经验要求",
                options=["不限", "1-3年", "3-5年", "5-10年", "10年以上"],
                value="3-5年",
            ).classes("w-full")

            education_select = ui.select(
                label="学历要求",
                options=["不限", "大专", "本科", "硕士", "博士"],
                value="本科",
            ).classes("w-full")

            with ui.row():
                ui.button("下一步", on_click=lambda: _on_step1_next(stepper, keyword_input, city_select, log))
                ui.button("重置", on_click=lambda: _reset_params(keyword_input, city_select, salary_min, salary_max, experience_select, education_select, log)).props("flat")

        # ── Step 2: 自动搜索 ──
        with ui.step("自动搜索"):
            ui.label("正在搜索候选人...").classes("text-h6")
            search_log = ui.log(max_lines=30).classes("w-full h-48")
            search_progress = ui.linear_progress(value=0).classes("w-full q-mt-sm")

            with ui.row():
                ui.button("开始搜索", on_click=lambda: _simulate_search(search_log, search_progress, stepper, log))
                ui.button("跳过", on_click=stepper.next).props("flat")

        # ── Step 3: AI筛选 ──
        with ui.step("AI筛选"):
            ui.label("候选人筛选结果").classes("text-h6")

            grid = ui.aggrid(
                {
                    "columnDefs": [
                        {"headerName": "姓名", "field": "name", "width": 80},
                        {"headerName": "职位", "field": "title", "width": 150},
                        {"headerName": "薪资", "field": "salary", "width": 100},
                        {"headerName": "经验", "field": "experience", "width": 80},
                        {"headerName": "学历", "field": "education", "width": 80},
                        {"headerName": "匹配度", "field": "score", "width": 90},
                    ],
                    "rowData": SAMPLE_CANDIDATES,
                    "rowSelection": "single",
                },
                theme="balham",
            ).classes("w-full h-64")

            selected_label = ui.label("请点击表格行选择候选人").classes("text-subtitle2 q-mt-md")

            async def on_row_clicked(e):
                if e.args.get("data"):
                    d = e.args["data"]
                    selected_label.text = f"已选择: {d['name']} — {d['title']} ({d['score']}分)"
                    log.push(f"选中候选人: {d['name']}")
                    ui.notify(f"已选择 {d['name']}", type="info")

            grid.on("rowClicked", on_row_clicked)

            with ui.row():
                ui.button("下一步：生成邀约", on_click=stepper.next)
                ui.button("上一步", on_click=stepper.previous).props("flat")

        # ── Step 4: 生成邀约 ──
        with ui.step("生成邀约"):
            ui.label("邀约预览").classes("text-h6")

            candidate_select = ui.select(
                label="选择候选人",
                options=[c["name"] for c in SAMPLE_CANDIDATES],
                value=SAMPLE_CANDIDATES[0]["name"],
                on_change=lambda: _update_invitation(candidate_select, md_preview, log),
            ).classes("w-full q-mb-md")

            md_preview = ui.markdown(
                INVITATION_TEMPLATE.format(**SAMPLE_CANDIDATES[0])
            ).classes("w-full q-pa-md")

            with ui.row():
                ui.button("发送邀约", on_click=lambda: _send_invitation(candidate_select, log))
                ui.button("上一步", on_click=stepper.previous).props("flat")


# ── 回调函数 ──────────────────────────────────────────────

def _on_step1_next(stepper, keyword_input, city_select, log):
    kw = keyword_input.value
    city = city_select.value
    log.push(f"搜索条件: 关键词={kw}, 城市={city}")
    ui.notify(f"条件已设置: {kw} @ {city}", type="positive")
    stepper.next()


def _reset_params(keyword_input, city_select, salary_min, salary_max, experience_select, education_select, log):
    keyword_input.value = "前端工程师"
    city_select.value = "北京"
    salary_min.value = 20
    salary_max.value = 50
    experience_select.value = "3-5年"
    education_select.value = "本科"
    log.push("参数已重置")
    ui.notify("参数已重置", type="info")


async def _simulate_search(search_log, progress, stepper, log):
    search_log.push("▶ 开始搜索...")
    steps = [
        (0.2, "正在连接 BOSS 直聘..."),
        (0.4, "正在获取职位列表..."),
        (0.6, "正在抓取候选人信息..."),
        (0.8, "正在解析简历数据..."),
        (1.0, "搜索完成！共找到 5 位候选人"),
    ]
    for val, msg in steps:
        await asyncio.sleep(0.8)
        progress.value = val
        search_log.push(msg)
        log.push(msg)
    await asyncio.sleep(0.5)
    ui.notify("搜索完成！", type="positive")
    stepper.next()


def _update_invitation(candidate_select, md_preview, log):
    name = candidate_select.value
    candidate = next(c for c in SAMPLE_CANDIDATES if c["name"] == name)
    md_preview.content = INVITATION_TEMPLATE.format(**candidate)
    log.push(f"邀约已更新: {name}")


def _send_invitation(candidate_select, log):
    name = candidate_select.value
    log.push(f"✅ 邀约已发送给 {name}")
    ui.notify(f"邀约已发送给 {name}！", type="positive")


# ── 启动 ──────────────────────────────────────────────

ui.run(native=True, title="Cassiel Agent Spike", port=8765)
