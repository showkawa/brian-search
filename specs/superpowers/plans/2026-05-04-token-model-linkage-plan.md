# Token → 模型选择 → 招聘页联动 实施计划

**Goal:** 设置页每条 Key 下增加模型选择器；招聘页模型选择器按已配置 Key 过滤。

**Spec:** docs/specs/2026-05-04-token-model-linkage.md

## Tasks

### Task 1: 提取 _MODEL_OPTIONS 到共享模块
- Create `src/cassiel/ui/model_options.py`
- 移入 `_MODEL_OPTIONS`, `parse_model_key()`, `all_model_labels()`, `key_from_label()`
- 新增 `get_models_for_provider()`, `get_available_providers()`, `get_available_model_labels()`, `get_missing_providers()`
- 更新 `recruit_page.py` 引用
- ✅ DONE

### Task 2: 设置页 — 每个 Key 下增加模型选择器
- Modify `src/cassiel/ui/settings_page.py`
- 每个 provider 增加 `ui.select`（模型列表按 provider 过滤）
- Key 为空时禁用选择器，连接测试成功时启用
- `_on_model_change()` 保存到 config.model
- ✅ DONE

### Task 3: 招聘页 — 模型过滤 + 未配置引导
- Modify `src/cassiel/ui/recruit_page.py`
- `build()` 顶部添加 API 状态检查横幅（无 Key 时显示橙色卡片）
- 模型选择器用 `get_available_model_labels()` 过滤选项
- 未配置 provider 显示文字提示
- ✅ DONE
