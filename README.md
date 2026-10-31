# Brian-Search

个人 AI / LLM 实验室，目前的主线产品是 **Cassiel Agent —— BOSS 直聘智能招聘助手**。

## 目录

| 路径 | 说明 |
|------|------|
| `agent_lab/cassiel_agent/` | **主项目**：搜索候选人 → LLM 打分筛选 → 生成邀约文案 → 确认后发送的桌面应用。详见 [README](agent_lab/cassiel_agent/README.md) |
| `ext_tool/cassiel_trans/` | Chrome MV3 扩展「Cassiel Translate」：划词/右键翻译选中文本 |
| `jupyter_lab/` | LLM 学习笔记：LangChain、LlamaIndex、scikit-learn、prompt / function-calling 等 |
| `.devin/` | Devin IDE 的 speckit 工作流与 `planning-with-files` skill |
| `specs/` | 需求规格（spec-driven 开发） |

## 快速开始（Cassiel Agent）

```powershell
cd agent_lab/cassiel_agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pip install playwright
playwright install chromium
python run.py
```

启动后窗口标题为「Cassiel Agent — HRD 智能助手」：

1. 在「📋 招聘Agent」页点登录，从本地 Chrome/Edge 提取 BOSS 直聘 Cookie（需先在浏览器登录过 `boss.zhipin.com`，并关闭浏览器）；
2. 填写搜索条件，运行流水线；
3. 候选人列表按 LLM 评分排序，勾选后生成邀约文案，逐条预览确认再发送；
4. 「⚙️ 账户配置」页填写 GLM / 通义 / DeepSeek 的 API Key（也可用环境变量 `GLM_API_KEY` / `QWEN_API_KEY` / `DEEPSEEK_API_KEY`）。

## 说明

- 配置文件、Cookie、SQLite 数据都放在 `agent_lab/cassiel_agent/` 下（打包后放在 exe 同目录），由 `cassiel.paths` 统一解析。
- `config.json` 内含本地 API Key，请勿提交到公开仓库。
