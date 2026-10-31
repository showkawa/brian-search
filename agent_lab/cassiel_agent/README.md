# Cassiel Agent

**BOSS 直聘智能招聘助手** —— 搜索、筛选、邀约一体化的 Agent 流水线，面向 Windows 的桌面应用。

> v1 范围：单岗位搜索；邀约文案由 LLM 生成，**人工预览确认后**才发送。

## 功能

| 步骤 | 模块 | 说明 |
|------|------|------|
| 1. 设定条件 | `ui/search_form.py` | 关键词、城市、薪资、经验、学历、翻页数 |
| 2. 采集候选人 | `collector/boss_client.py` | 纯 HTTP 调用 BOSS 直聘 wapi 搜索接口；Cookie 从本地 Chrome/Edge 提取 |
| 3. LLM 筛选 | `evaluator/filter.py` | 薪资 25 / 经验 25 / 学历 20 / 岗位相关性 30 打分，输出 0–100 分与理由，按分排序取 Top N |
| 4. 生成邀约 | `writer/invitation.py` | 结合候选人背景与岗位 JD 生成个性化文案（100–200 字） |
| 5. 确认并发送 | `writer/sender.py` | Playwright 打开聊天页、模拟输入；发送间隔 ≥ 10s，逐条确认 |

支持三家 OpenAI 兼容的 LLM：**GLM（智谱）/ Qwen（通义）/ DeepSeek**，三个环节可分别选择模型。

## 架构

```
run.py
└── ui/main.py            NiceGUI 原生窗口（侧边栏 + 招聘 / 设置两页）
    ├── ui/recruit_page.py        登录栏 + 4 步 Stepper
    ├── ui/candidate_table.py     候选人表格（评分/排序）
    ├── ui/invitation_preview.py  文案预览与逐条确认
    └── ui/settings_page.py       API Key / 模型清单 / 搜索默认值

agent/orchestrator.py    DAG 流水线：阶段链、类型化状态传递、重试、熔断、日志回调
agent/roles.py           搜索员 / 评估员 / 文案员 三个角色与其 system prompt
paths.py                 统一路径：config.json / cookies.json / data/cassiel.db
config/settings.py       dataclass 配置模型（config.json 读写）
session/store.py         SQLite：搜索历史、候选人缓存、邀约记录
llm/providers.py         GLM / Qwen / DeepSeek 统一适配层
models/candidate.py      候选人数据模型
```

## 运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pip install playwright
playwright install chromium

python run.py
```

### 配置

- 首次运行后在「⚙️ 账户配置」页填写 API Key，保存即写入本目录的 `config.json`；
- 也可用环境变量覆盖：`GLM_API_KEY`、`QWEN_API_KEY`、`DEEPSEEK_API_KEY`；
- 登录：先在 Chrome/Edge 中登录 `boss.zhipin.com`，关闭浏览器，再在招聘页点登录以提取 Cookie（只存 Cookie，不存密码）；
- 运行期文件位置：`config.json`、`cookies.json`、`data/cassiel.db`（打包后为 exe 同目录）。

### 测试

```powershell
pytest tests/unit -q        # 单元测试，无网络
pytest tests/ -q            # 含端到端用例（需要 Playwright 与 API Key）
```

## 打包

```powershell
python build_nuitka.py --clean     # Nuitka standalone → dist/CassielAgent/
makensis installer.nsi            # NSIS 安装包
# 或：pyinstaller cassiel-agent.spec
```

安装包体积预算 ≤ 250MB（Playwright Chromium 约 100MB）。

## 安全约束

- 只保存 Cookie，不保存 BOSS 直聘密码；
- 操作节流：搜索间隔 ≥ 5s、翻页 ≥ 3s、发送 ≥ 10s，单次候选 ≤ 50、发送 ≤ 10；
- 每条邀约必须人工确认，不做批量群发；
- `config.json` 含 API Key，已被 git 跟踪过历史，**不要提交新密钥**；建议改用环境变量。
