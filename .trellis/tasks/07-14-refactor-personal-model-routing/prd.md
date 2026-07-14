# 拆 PersonalModelRouting.vue（2684 行→<500）

## Goal

将 `frontend/src/components/llm-settings/PersonalModelRouting.vue`（2684 行，5 大组件之首）拆分至 <500 行，运行时行为 100% 等价。属 parent `07-12-engineering-baseline` acceptance 第 4 项「5 大前端组件 <500 行」的子项。

## 现状

- 路径：`frontend/src/components/llm-settings/PersonalModelRouting.vue`，2684 行。
- 调用方：`LLMSettings.vue`、`SettingsView.vue`（2 处 dynamic 渲染 `<PersonalModelRouting>`）。
- **测试覆盖：无**（codegraph 未发现覆盖测试）——拆分前须先补关键路径测试或固化手测清单。
- 职责：用户个人 LLM 模型路由配置——chat/tts/embedding 三分区（`activeSection`）、provider 模型选择器弹窗（`openProviderModelPicker`/`closeModelPicker`/`savePickerSelections`/`setPrimaryChatModelById`/`selectEmbeddingModel`/`saveTTSSelection`，含弹窗定位与外部点击确认）、模型加载（`loadBundle`）与保存（`saveRoutes`）。

## Requirements

- 主组件降至 <500 行，抽出内聚子组件 / composable。
- 行为等价：分区切换、模型选择器弹窗开关/定位/外部点击确认、各能力保存、`emit('saved')` 均不变。
- Vue scoped style 随 template 迁移（父 scoped CSS 不作用于子组件内部，参考 parent design.md Slice D 范式）。
- 三件套绿：`vue-tsc --noEmit` exit 0 / `vitest run` 全绿 / `eslint` 0 新增 error。
- 因无既有测试，首块拆分前先补关键路径测试（分区切换 + 模型选择 + 保存）或固化手测清单作为回归网。

## Acceptance Criteria

- [ ] `PersonalModelRouting.vue` < 500 行。
- [ ] 三件套全绿（vue-tsc / vitest / eslint 0 新增）。
- [ ] 行为等价（测试或手测清单覆盖分区切换/模型选择/保存）。
- [ ] 抽出的子组件补 AIMETA 首行（同 workspace 子组件惯例）。

## Notes

- 复杂任务：`task.py start` 前补 `design.md`（拆分边界契约表）+ `implement.md`（逐块清单 + 验证 + 回滚点）。
- parent：`07-12-engineering-baseline`（acceptance 第 4 项）。
