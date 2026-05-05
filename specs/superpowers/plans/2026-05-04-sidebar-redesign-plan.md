# Cassiel Agent V1 侧边栏重构 实施计划

**Goal:** 将 Cassiel Agent 从单页 Stepper 重构为左侧边栏导航 + 双页面架构。

**Architecture:** AppShell 外壳 (ui.left_drawer + ui.tab_panels)，RecruitPage + SettingsPage 两个页面。

**Spec:** docs/specs/2026-05-04-sidebar-redesign.md

## Tasks

### Task 1: 扩展配置模型
- Modify `src/cassiel/config/settings.py`
- 新增 `CredentialEntry` + `CredentialsConfig` dataclass
- `AppConfig` 添加 `credentials` 字段，更新 from_json/to_json
- ✅ DONE

### Task 2: 侧边栏组件 sidebar.py
- Create `src/cassiel/ui/sidebar.py`
- Sidebar 类：品牌标识 + 2 菜单项 + 版本号
- ✅ DONE

### Task 3: 提取招聘页面 recruit_page.py
- Create `src/cassiel/ui/recruit_page.py`
- 从 main.py CassielApp 提取 RecruitPage 类
- ✅ DONE

### Task 4: 账户配置页 settings_page.py
- Create `src/cassiel/ui/settings_page.py`
- 3 个区块：大模型 API / 外部凭据 / 搜索默认值
- ✅ DONE

### Task 5: 重写 main.py 为 AppShell
- Rewrite `src/cassiel/ui/main.py`
- 711→74 行，纯外壳：侧边栏 + tab_panels 路由
- ✅ DONE

### Task 6: 更新 __init__.py 文档
- ✅ DONE

### Task 7: 集成测试
- 修复 `ui.button(disabled=True)` → `.props("disabled")`
- 修复 drawer 消失 → `fixed=True`
- ✅ DONE
