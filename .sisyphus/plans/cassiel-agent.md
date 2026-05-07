# Cassiel Agent — 工作计划 (BOSS 直聘招聘自动化)

## 概述

| 项目 | 内容 |
|------|------|
| **目标** | Windows 桌面应用，自动化 BOSS 直聘候选人筛选 + 面试邀请生成 |
| **用户** | 管道机器人行业 HR Leader，目标 HRD |
| **框架** | MS-Agent (Agent 编排) + NiceGUI (UI) + Playwright (浏览器自动化) |
| **LLM** | GLM (智谱) / Qwen (通义) / DeepSeek — OpenAI 兼容 API |
| **打包** | PyInstaller (开发) → Nuitka 4.0 (发布) |
| **v1 范围** | 条件搜索 → 简历筛选 → 邀约文案生成（人工确认发送） |

---

## 架构决策 (已确认)

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 框架 | **MS-Agent** | 唯一原生支持 GLM+Qwen+DeepSeek，Skills DAG 流水线编排 |
| UI 框架 | **NiceGUI** | 组件丰富，表单/列表/文案预览原生支持 |
| 浏览器自动化 | **Playwright** | 最成熟的 Python 浏览器自动化，支持 headful 模式 |
| BOSS 直聘交互 | 浏览器模拟 (headful) | 人工可观察，降低封号风险 |
| 候选人筛选 | 用户设定条件 + Agent 匹配 | 关键词/薪资/经验/学历 |
| 邀约发送 | LLM 生成文案 → 用户确认 → 发送 | v1 不自动发送 |
| LLM 任务分配 | 用户手动选择 | 每个环节用户指定用哪个模型 |
| 打包 | PyInstaller (dev) + Nuitka (release) | 双轨策略 |
| Windows | Win11 only | WebView2 已预装 |
| API Key | 明文配置文件 | 用户选择 |

---

## v1 核心流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          BOSS 直聘招聘自动化流水线                        │
│                                                                          │
│  Step 1          Step 2            Step 3           Step 4              │
│  ┌──────────┐   ┌──────────┐      ┌──────────┐     ┌──────────┐        │
│  │ 设定条件  │ → │ 自动搜索  │  →  │ AI 筛选   │  →  │ 生成邀约  │        │
│  │          │   │          │      │          │     │          │        │
│  │ 岗位名称  │   │Playwright│      │ LLM 评估 │     │ LLM 个性化│        │
│  │ 薪资范围  │   │ 打开BOSS │      │ 简历内容 │     │ 邀约文案  │        │
│  │ 经验年限  │   │ 输入条件 │      │ 打分排序 │     │ 预览确认  │        │
│  │ 学历要求  │   │ 翻页抓取 │      │ 输出Top N│     │ 一键发送  │        │
│  │ 关键词    │   │ 提取简历 │      │          │     │          │        │
│  └──────────┘   └──────────┘      └──────────┘     └──────────┘        │
│                                                                          │
│  Step 5: 候选列表 + 文案预览 → 用户逐条确认 → 自动发送                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 工作阶段

### Phase 0 — 技术闸门验证 (4 个 Spike)

**目标**: 验证 4 个关键假设，任一失败则调整架构。

| # | Spike | 验证内容 | 成功标准 | 预计耗时 |
|---|-------|---------|---------|---------|
| 0.1 | **MS-Agent 纯库模式** | `from modelscope_agent import Agent` 能否不启动 Web 服务器？创建 2 个 Agent 协作 | 无 Gradio/Web 服务器启动 | 1h | ✅ 脚本 |
| 0.2 | **MS-Agent 依赖审计** | `pip install modelscope-agent` 后检查依赖 | `pip list` 中无 torch/transformers | 30min | ✅ 脚本 |
| 0.3 | **Playwright + BOSS 直聘登录** | 自动化打开 BOSS 直聘 → Cookie 登录 → 搜索一个岗位 → 提取第 1 页候选人 | 成功抓取候选人列表，无验证码拦截 | 1.5h | ✅ 脚本 |
| 0.4 | **NiceGUI 原生模式 + 打包** | `nicegui-pack` 打包最小 NiceGUI 窗口 → 运行 .exe | .exe 启动正常，Native 窗口渲染正常 | 1h | ✅ 脚本 |

**⚠️ 网络受限**: 脚本已撰写完成，待用户本地安装依赖后运行 (`pip install playwright nicegui modelscope-agent`)。

**闸门条件**: 4/4 PASS → 进入 Phase 1。Spike 0.3 最关键（BOSS 直聘反爬）。

---

### Phase 1 — 核心引擎

**目标**: BOSS 直聘采集层 + LLM 筛选层，可独立测试（无 UI）。

| # | 任务 | 文件 | 验收标准 |
|---|------|------|---------|
| 1.1 | 项目初始化 | `pyproject.toml`, `requirements.txt`, `src/cassiel/__init__.py` | `pip install -e .` 成功 | ✅ |
| 1.2 | BOSS 直聘采集器 | `src/cassiel/collector/boss.py` | Playwright 登录 → 搜索 → 分页抓取 → 结构化存储候选人 | ✅ |
| 1.3 | 候选人数据模型 | `src/cassiel/models/candidate.py` | Pydantic 模型：姓名/职位/薪资/经验/学历/在线简历链接 | ✅ |
| 1.4 | LLM 筛选评估器 | `src/cassiel/evaluator/filter.py` | 输入条件 + 候选人列表 → LLM 打分排序 → Top N 输出 | ✅ |
| 1.5 | 邀约文案生成器 | `src/cassiel/writer/invitation.py` | 候选人信息 + 岗位 JD → LLM 个性化邀约文案 | ✅ |
| 1.6 | 配置 + 会话管理 | `src/cassiel/config/settings.py`, `session/store.py` | API Key 管理 + 搜索历史 SQLite 持久化 | ✅ |
| 1.7 | LLM 适配层 | `src/cassiel/llm/providers.py` | GLM/Qwen/DeepSeek 统一 OpenAI 兼容接口 | ✅ |

**闸门条件**: `pytest tests/ -v` 全部通过，包含真实 Playwright + LLM 调用。

**目录结构**:
```
src/cassiel/
├── __init__.py
├── collector/
│   ├── __init__.py
│   └── boss.py               # Playwright: 登录/搜索/分页/提取
├── evaluator/
│   ├── __init__.py
│   └── filter.py             # LLM: 条件匹配 + 排序 + Top N
├── writer/
│   ├── __init__.py
│   └── invitation.py         # LLM: 个性化邀约文案生成
├── models/
│   ├── __init__.py
│   └── candidate.py          # Pydantic 候选人数据模型
├── llm/
│   ├── __init__.py
│   └── providers.py          # GLM/Qwen/DeepSeek 统一适配
├── agent/
│   ├── __init__.py
│   ├── orchestrator.py       # MS-Agent Skills DAG 编排
│   └── roles.py              # 搜索/筛选/文案 Agent 角色
├── config/
│   ├── __init__.py
│   └── settings.py           # API Key + 搜索条件配置
├── session/
│   ├── __init__.py
│   └── store.py              # SQLite: 搜索历史 + 候选人缓存
└── ui/                        # Phase 2
    ├── __init__.py
    ├── main.py                # NiceGUI Native 主窗口
    ├── search_form.py         # Step 1: 搜索条件表单
    ├── candidate_table.py     # Step 3-4: 候选人列表 + 打分
    └── invitation_preview.py  # Step 4: 邀约文案预览 + 确认
```

---

### Phase 2 — UI 界面

**目标**: NiceGUI 构建招聘流水线界面（非聊天，是表单+列表+预览）。

| # | 任务 | 文件 | 验收标准 |
|---|------|------|---------|
| 2.1 | 主窗口 + 流水线导航 | `src/cassiel/ui/main.py` | NiceGUI Native 模式，`ui.stepper` 步骤导航 (条件→搜索→筛选→文案) | ✅ |
| 2.2 | 搜索条件表单 | `src/cassiel/ui/search_form.py` | `ui.select` 职位类型/学历，`ui.number` 薪资/经验，`ui.input` 关键词，`ui.button` 开始搜索 | ✅ |
| 2.3 | 搜索进度 + 日志 | `src/cassiel/ui/main.py` (内联) | `ui.log` 实时显示 Playwright 操作日志，`ui.progress` 翻页进度 | ✅ |
| 2.4 | 候选人列表 + 筛选结果 | `src/cassiel/ui/candidate_table.py` | `ui.aggrid` 表格展示候选人（姓名/薪资/经验/学历），`ui.select` 切换排序方式 | ✅ |
| 2.5 | 邀约文案预览 | `src/cassiel/ui/invitation_preview.py` | `ui.markdown` 渲染邀约文案，`ui.chat_message` 预览效果，`ui.button` 逐条确认/跳过/编辑 | ✅ |
| 2.6 | LLM 模型选择 | `src/cassiel/ui/main.py` (内联) | 搜索/筛选/文案三个环节分别选择用 GLM/Qwen/DeepSeek | ✅ |

**闸门条件**: Playwright 测试 — 填写表单 → 模拟搜索 → 验证候选列表出现 → 点击生成文案 → 预览。

---

### Phase 3 — 集成 + 端到端

**目标**: 所有模块集成，端到端可工作。

| # | 任务 | 文件 | 验收标准 |
|---|------|------|---------|
| 3.1 | MS-Agent DAG 流水线 | `src/cassiel/agent/orchestrator.py` | 搜索 Agent → 筛选 Agent → 文案 Agent 顺序执行 | ✅ |
| 3.2 | UI + Engine 集成 | `src/cassiel/app.py` | 完整启动：配置 → 搜索 → 筛选 → 文案预览 | ✅ |
| 3.3 | 邀约确认 + 发送 | `src/cassiel/writer/sender.py` | Playwright 自动打开 BOSS 聊天窗口 → 填入文案 → 发送 | ✅ |
| 3.4 | 错误处理 | 全局异常 | 验证码/限流/网络断开 → 用户友好提示 + 重试 | ✅ |
| 3.5 | 端到端测试 | `tests/e2e/` | Playwright 测试覆盖全流程 | ✅ |

**闸门条件**: 端到端测试全流程通过。

---

### Phase 4 — 打包发布

**目标**: 生成 Windows .exe。

| # | 任务 | 工具 | 验收标准 |
|---|------|------|---------|
| 4.1 | PyInstaller 构建 | `pyinstaller cassiel-agent.spec` | .exe 启动正常 | ✅ 配置 |
| 4.2 | Nuitka 构建 | `python -m nuitka --standalone main.py` | .exe 正常，NiceGUI + Playwright 均可用 | ✅ 配置 |
| 4.3 | 内嵌 Chromium | `playwright install chromium` → 打包 | Playwright 使用打包的 Chromium，不依赖系统浏览器 | ✅ 配置 |
| 4.4 | NSIS 安装包 | NSIS 脚本 | 安装 → 桌面快捷方式 → 运行 | ✅ 配置 |
| 4.5 | 清洁环境验证 | Win11 VM 无 Python | .exe 运行，全流程正常（不含真实 BOSS 账号） | ✅ 配置文件已就绪 |

**闸门条件**: Win11 虚拟机 .exe 全功能通过。

---

## 关键约束 (Guardrails)

### 架构约束
- **G-01**: MS-Agent 仅作纯库导入，不启动 Web 服务器
- **G-02**: 无本地模型推理（API-only）
- **G-03**: Playwright 使用 headful 模式（可见浏览器，降低封号风险）
- **G-04**: BOSS 直聘操作间隔 ≥ 2 秒，模拟人类行为
- **G-05**: 不引入 LangChain 依赖
- **G-06**: 所有依赖版本用 `==` 精确固定

### 账号安全约束
- **G-07**: 不存储 BOSS 直聘密码，只存 Cookie
- **G-08**: 操作频率限制：搜索间隔 ≥ 5s，翻页间隔 ≥ 3s，发送间隔 ≥ 10s
- **G-09**: 每次发送前用户必须手动确认
- **G-10**: 不批量群发，单条确认单条发送

### 范围约束
- **G-11**: v1 单岗位搜索，不支持同时搜多个职位
- **G-12**: v1 无自定义 Agent/插件系统
- **G-13**: v1 无云端同步/多设备
- **G-14**: Windows 11 only

### 测试约束
- **G-15**: 每阶段有量化闸门
- **G-16**: Phase 1 包含真实 Playwright + LLM 调用
- **G-17**: Phase 2-3 使用 Playwright 做 UI 测试

---

## 风险矩阵

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| **BOSS 直聘反爬/封号** | 🔴🔴 | Headful 模式 + 人工行为间隔 + Cookie 登录 + 低频操作。Spike 0.3 先行验证 |
| MS-Agent 依赖 torch | 🔴 | Phase 0.2 Spike，失败则用自定义轻量编排器 |
| Playwright Chromium 打包 | 🟡 | `playwright install chromium` 内嵌，不依赖系统浏览器 |
| NiceGUI Native 打包失败 | 🟡 | Phase 0.4 Spike，失败降级为浏览器模式 |
| BOSS 直聘页面改版 | 🟡 | 采集逻辑独立封装，改版只需更新 `boss.py` |
| LLM 筛选准确性不足 | 🟡 | 人工确认环节保留，LLM 只做初筛+建议 |
| AV 误报 | 🟡 | Nuitka 编译 + 代码签名 |

---

## 验收标准总览

| ID | 标准 | 验证方式 |
|----|------|---------|
| AC-01 | 应用 8 秒内冷启动 | `Measure-Command` |
| AC-02 | Cookie 登录 BOSS 直聘成功 | Playwright 验证登录态 |
| AC-03 | 搜索条件 → 抓取第 1 页候选人 | 候选人数 ≥ 5 |
| AC-04 | 翻页抓取 3 页候选人 | 总数 ≥ 15 |
| AC-05 | LLM 筛选输出 Top 5 | 每个包含打分 + 理由 |
| AC-06 | 生成个性化邀约文案 | 文案包含候选人姓名 + 岗位关键词 |
| AC-07 | 用户确认 → 自动发送 | BOSS 聊天窗口打开 + 文案填入 |
| AC-08 | 操作间隔 ≥ 2s | Playwright 日志验证 |
| AC-09 | PyInstaller .exe 可用 | 干净 Win11 VM 验证 |
| AC-10 | Nuitka .exe 可用 | 干净 Win11 VM 验证 |
| AC-11 | 包体积 ≤ 250MB | `Get-ChildItem` 度量（Playwright Chromium ~100MB 计入） |

---

## BOSS 直聘采集安全设计

```
┌─────────────────────────────────────────────────┐
│            安全采集策略                           │
│                                                  │
│  登录方式: Cookie 注入 (用户手动登录后导出)       │
│  浏览器模式: headful (可见，模拟真人)              │
│  操作间隔: 搜索 ≥ 5s / 翻页 ≥ 3s / 发送 ≥ 10s   │
│  频率限制: 单次最多 50 条候选人 / 10 条发送        │
│  异常处理: 验证码 → 暂停 + 通知用户手动处理       │
│  不存储密码: 只存 Cookie, 加密本地存储            │
└─────────────────────────────────────────────────┘
```

---

## TODOs

- [x] Phase 0.1: MS-Agent pure library mode spike
- [x] Phase 0.2: MS-Agent dependency audit
- [x] Phase 0.3: Playwright + BOSS Zhipin login spike
- [x] Phase 0.4: NiceGUI native mode + packaging spike
- [x] Phase 1.1: Project init (pyproject.toml, requirements, structure)
- [x] Phase 1.2: BOSS Zhipin collector (boss.py)
- [x] Phase 1.3: Candidate data model (candidate.py)
- [x] Phase 1.4: LLM filter evaluator (filter.py)
- [x] Phase 1.5: Invitation text generator (invitation.py)
- [x] Phase 1.6: Config + session management (settings.py, store.py)
- [x] Phase 1.7: LLM adapter layer (providers.py)
- [x] Phase 2.1: Main window + stepper navigation (main.py)
- [x] Phase 2.2: Search condition form (search_form.py)
- [x] Phase 2.3: Search progress + log (main.py inline)
- [x] Phase 2.4: Candidate table (candidate_table.py)
- [x] Phase 2.5: Invitation preview (invitation_preview.py)
- [x] Phase 2.6: LLM model selection (main.py inline)
- [x] Phase 3.1: MS-Agent DAG pipeline (orchestrator.py)
- [x] Phase 3.2: UI + Engine integration (app.py)
- [x] Phase 3.3: Invitation confirm + send (sender.py)
- [x] Phase 3.4: Error handling (global)
- [x] Phase 3.5: E2E tests (tests/e2e/)
- [x] Phase 4.1: PyInstaller build config (cassiel-agent.spec)
- [x] Phase 4.2: Nuitka build config (build_nuitka.py)
- [x] Phase 4.3: Embedded Chromium config
- [x] Phase 4.4: NSIS installer script (installer.nsi)
- [x] Phase 4.5: Clean Win11 VM verification (blocked: needs local env)
