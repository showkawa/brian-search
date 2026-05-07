# 动态模型选择 — 设计文档

> **目标**: 模型列表改为从提供商 API 动态获取，用户勾选启用，招聘页只显示已启用的模型，名称保持原始 ID。

## 一、现状

| 问题 | 描述 |
|------|------|
| 模型列表硬编码 | `model_options.py` 写死 8 个模型，新模型需改代码 |
| 自定义标签 | 显示 "GLM-4 Flash (智谱) — 快速" 而非原始 ID |
| 无启用开关 | 用户无法控制哪些模型可选，固定展示全量 |
| 测试连接无后续 | `models.list()` 只验证 Key，不展示模型列表 |

## 二、目标

1. 连接测试成功后，从 API 拉取提供商的全部模型
2. checklist 展示全部模型，用户勾选启用哪些
3. 模型名使用提供商原始 ID（如 `deepseek-chat`），不加中文别名
4. checklist 全选/取消全选，勾选变更即时保存
5. 显示拉取状态和时间戳
6. 招聘页三个模型下拉只显示已启用的模型
7. 无可用模型时给出导航引导

## 三、数据模型变更

### `config.json` 新增

```json
"enabled_models": {
    "deepseek": ["deepseek-chat", "deepseek-coder"],
    "glm": ["glm-4-flash", "glm-4-plus", "glm-4"],
    "qwen": ["qwen-turbo", "qwen-plus", "qwen-max"]
},
"model_refreshed_at": {
    "deepseek": "2026-05-05T14:30:00",
    "glm": "2026-05-05T14:31:00",
    "qwen": ""
}
```

### `settings.py` 新增字段

```python
@dataclass
class AppConfig:
    enabled_models: dict[str, list[str]] = field(default_factory=dict)
    model_refreshed_at: dict[str, str] = field(default_factory=dict)
```

## 四、设置页 UI

```
┌────────────────────────────────────────────────────────────┐
│  DeepSeek    [sk-abc...]   [⏳ 测试中]   ✓ 已连接           │
│              🔄 已拉取 2 个模型                             │
│              ┌─ 默认模型: [deepseek-chat ▼]               │
│              │                                              │
│              │  [全选] [取消全选]                            │
│              │  ☑ deepseek-chat                            │
│              │  ☑ deepseek-coder                           │
│              │                                              │
│              │  上次更新: 2026-05-05 14:30                   │
│              └────────────────────────────────────────────┘
├────────────────────────────────────────────────────────────┤
│  智谱 GLM    [sk-xxx...]   [测试连接]   未配置               │
│              ⚠ 请先测试连接以获取可用模型                     │
├────────────────────────────────────────────────────────────┤
│  通义 Qwen   [          ]   [测试连接]   未配置               │
│              (Key 为空时不显示任何提示)                       │
└────────────────────────────────────────────────────────────┘
```

### 状态流转

| 状态 | 展示 |
|------|------|
| Key 为空 | 不显示 checklist / 下拉 |
| Key 已填，未测试 | "⚠ 请先测试连接以获取可用模型" |
| 测试中 | spinner + "连接测试中..." |
| 测试成功 | "✓ 已连接" + "🔄 已拉取 N 个模型" + checklist(全选) |
| 拉取模型失败 | "✓ 已连接" + "✗ 模型列表拉取失败" |
| Key 变更 | checklist 清空 + "⚠ API Key 已变更，请重新测试连接" |

## 五、招聘页 UI

| 情况 | 展示 |
|------|------|
| 有已启用模型 | 三个下拉框正常显示已启用模型 |
| 无任何已启用模型 | "⚠ 暂无可用模型，请先在左侧「⚙️ 账户配置」中测试连接并启用模型"，三个下拉隐藏 |

## 六、关键逻辑

| 场景 | 行为 |
|------|------|
| 全选按钮 | 一键勾选所有模型 |
| 取消全选 | 一键取消全部 |
| 取消勾选当前默认模型 | 默认模型自动回退到第一个已启用 |
| checklist 勾选变更 | 立即保存到 config.json |
| 连接测试成功 | 拉取全部模型 → 全选 → 保存 |
| Key 变更 | 清空 checklist + 清空 enabled_models + 提示重测 |

## 七、修改清单

| 文件 | 变更 |
|------|------|
| `llm/providers.py` | `LLMProvider` 基类新增 `list_models()` |
| `config/settings.py` | 新增 `enabled_models` + `model_refreshed_at` 字段，级联保存/加载 |
| `ui/model_options.py` | 删除 `_MODEL_OPTIONS`，函数改为从 config 读取 |
| `ui/settings_page.py` | 核心改造：checklist + 全选 + 状态标签 + 时间戳 |
| `ui/recruit_page.py` | 下拉约束到已启用模型 + 空模型引导 |
| `config.json` | 新增 `enabled_models` + `model_refreshed_at` |
