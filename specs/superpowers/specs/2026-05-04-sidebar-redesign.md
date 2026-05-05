# Cassiel Agent V1 侧边栏重构设计

**日期**: 2026-05-04
**状态**: 已确认

## 背景

当前 Cassiel Agent 是单页应用，4 步 Stepper 工作流直接展示在页面上。随着功能扩展，需要将 BOSS 直聘招聘助手定位为子 Agent 之一，引入侧边栏导航支持多页面。

## 目标

将现有单页 Stepper 重构为侧边栏多页面架构，V1 包含两个页面：招聘Agent、账户配置。

## 设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 侧边栏样式 | 固定 200px，文字+图标 | V1 只有 2 个菜单项，文字标签直观 |
| 首页 | 无独立首页，默认进入招聘Agent | V1 不需要仪表盘 |
| 模型选择器位置 | 保留在招聘Agent页面顶部 | 方便每次搜索前调整，配置页只存默认值 |
| 页面切换机制 | `ui.left_drawer` + `ui.tab_panels` | NiceGUI 原生模式兼容 |
| 配置页范围 | 通用凭据管理（大模型 API + 外部网站 + 搜索默认值） | 不限于大模型，包含所有需要用户认证的外部服务 |

## 架构

### 整体布局

```
┌──────────────┬─────────────────────────────────────────┐
│  Cassiel     │  📋 招聘Agent                           │
│  HRD 智能助手│                                         │
│              │  [模型: 🔍GLM-4 📊DeepSeek ✍️Qwen+]    │
│  📋 招聘Agent│  [操作日志]                              │
│  ⚙️ 账户配置 │  [4步Stepper]                           │
│              │    ①设置条件 → ②自动搜索 → ③AI筛选 → ④邀约│
│              │                                         │
│  v0.1.0      │                                         │
└──────────────┴─────────────────────────────────────────┘
```

### 代码结构变更

**重构前** (main.py ~711 行):
```
CassielApp
  └── _build_ui()  # 单体方法：标题+日志+模型选择+Stepper
```

**重构后**:
```
AppShell           # 侧边栏 + 页面容器
  ├── left_drawer  # 固定侧边栏，菜单项
  └── tab_panels   # 页面切换容器
      ├── RecruitPage    # 招聘Agent页（从 CassielApp 提取）
      └── SettingsPage   # 账户配置页（新增）
```

### 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `ui/main.py` | 重写 | `CassielApp` → `AppShell`，只负责侧边栏+路由 |
| `ui/recruit_page.py` | 新建 | 从 main.py 提取招聘相关 UI 和逻辑 |
| `ui/settings_page.py` | 新建 | 账户配置页面 |
| `ui/sidebar.py` | 新建 | 侧边栏组件（菜单项、版本号） |
| `ui/search_form.py` | 不变 | 复用现有组件 |
| `ui/candidate_table.py` | 不变 | 复用现有组件 |
| `ui/invitation_preview.py` | 不变 | 复用现有组件 |
| `config/settings.py` | 扩展 | 新增 `credentials` 字段存储外部网站凭据 |
| `run.py` | 不变 | 入口不变 |

## 不做的事情 (V1)

- ❌ 独立首页/仪表盘
- ❌ 可折叠侧边栏
- ❌ 更多菜单项（培训、考勤等）
- ❌ LinkedIn/其他招聘平台集成
- ❌ 多用户/权限系统
- ❌ 数据库迁移（继续用 SQLite + config.json）
