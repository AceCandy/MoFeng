# implement.md — 拆 PersonalModelRouting.vue 执行清单

> 配合 design.md。每个 Slice 独立 commit，三件套绿后 push。逐 slice 在 design.md roadmap 表回填实测行数 + commit hash。

## 前置（Slice 0：规划收尾，本会话完成）

- [x] 读全文（template L1-535 / script L537-1772），梳理 82 符号归属
- [x] 写 design.md（边界契约表 + roadmap + 测试策略）
- [ ] 写 implement.md（本文件）+ manual-checklist.md
- [ ] 配置 implement.jsonl / check.jsonl
- [ ] review gate → `python3 ./.trellis/scripts/task.py start 07-14-refactor-personal-model-routing`

## Slice 1 — stageDefinitions.ts + modelRoutingTypes.ts（极低风险）

**目标**：抽 stageGroups 145 行纯静态数据 + 公共类型。

- [ ] 建 `frontend/src/components/llm-settings/modelRoutingTypes.ts`：迁 `Capability`/`RoutingSection`/`ProviderFormMode`/`ReadinessTone`/`StageDefinition`/`StageGroup`/`ProviderForm`/`ProviderFetchState`/`ReadinessSummary`
- [ ] 建 `frontend/src/components/llm-settings/stageDefinitions.ts`：export `stageGroups: StageGroup[]`（L624-764 原样迁出）
- [ ] 主组件删本地 stageGroups + 类型定义，改 `import { stageGroups } from './stageDefinitions'` + types import
- [ ] 验证：三件套 + `wc -l`（2684 → ~2540）
- [ ] 回滚点：单 commit，`git revert` 即回

## Slice 2 — modelRoutingHelpers.ts + createModelPayload 单测

- [ ] 建 `modelRoutingHelpers.ts`：迁纯函数 `createModelPayload`/`modelDisplayName`/`activeModelCapability`/`providerCapabilities`/`createProviderCapabilities`/`providerTypeLabels`（参数化）
- [ ] 主组件 import 替换；`groupModelsByProvider` 参数化 models 入参
- [ ] 建 `modelRoutingHelpers.spec.ts`：createModelPayload 三分支 + activeModelCapability + modelDisplayName
- [ ] 验证：三件套（vitest 含新 spec）+ wc
- [ ] review gate：helpers 纯函数化后调用点签名兼容

## Slice 3 — useModelBundle composable

- [ ] 建 `useModelBundle.ts`：bundleQuery + 9 mutation + providers/models/isLoading/isSavingProvider/isSavingRoutes + feedback/setFeedback + loadBundle + watch(bundleQuery.error)
- [ ] 主组件解构替换；onMounted 内 loadBundle 调用留主或入参回调
- [ ] 验证：三件套 + wc

## Slice 4 — useSectionMeta composable

- [ ] 建 `useSectionMeta.ts`：sectionEyebrow/heading/description/readinessSummary + enabled/default computed 群 + activeProviders + chatModelsByProvider 等
- [ ] 入参透传 bundle(providers/models) + activeSection + routeSelections/allStageKeys
- [ ] 验证：三件套 + wc

## Slice 5 — useStageRoutes composable

- [ ] 建 `useStageRoutes.ts`：routeSelections/initialRouteSelections + chatStageGroups/allStageKeys + syncRouteSelectionsFromBundle + saveRoutes + isDirty(routes 分支) + watch(bundleQuery.data→sync)
- [ ] 入参透传 bundle + saveStageRoutesMutation + providerFormMode（isDirty 用）
- [ ] defineExpose isDirty 改读 composable 返回
- [ ] 验证：三件套 + wc + 手测 routes 保存/isDirty

## Slice 6 — useProviderForm composable

- [ ] 建 `useProviderForm.ts`：providerForm/providerFormMode/editingProviderId + emptyProviderForm/assignProviderForm + begin/create/edit/cancel/saveProviderForm + toggleProviderEnabled/deleteProviderFromCard + providerFetchStates/providerFetchState
- [ ] 入参透传 bundle + activeModelCapability + mutations + loadBundle
- [ ] defineExpose save 的 providerFormMode 分支改读 composable 返回
- [ ] 验证：三件套 + wc + 手测供应商 CRUD

## Slice 7 — useModelPicker composable（最高风险）

- [ ] 建 `useModelPicker.ts`：弹窗状态机（activeModelPickerProviderId/position/refs/query/pending sets/isSavingPicker）+ openProviderModelPicker/closeModelPicker/updateModelPickerPosition/loadProviderModels/enabledChatModelNamesFor + isModelPickerActive/isModelPickerOpen/modelPickerStyle/isChatPickerDirty + setModelPickerDialogRef/setModelPickerSearchInputRef + onPickerClickOutside/onPickerViewportChange + useDialogA11y + onMounted/onBeforeUnmount 监听注册 + watch(activeSection/activeProviders→close)
- [ ] **保留 id 选择器 hack + 函数 ref**
- [ ] 入参透传 bundle + activeSection + sectionMeta(defaultTTSModel/ttsModelsByProvider) + selection(save 方法透传)
- [ ] 验证：三件套 + wc + 手测弹窗定位/外部点击/视口关闭
- [ ] review gate：循环依赖（save 透传）解构顺序

## Slice 8 — useModelSelection composable

- [ ] 建 `useModelSelection.ts`：upsertModelForCapability/togglePendingChatModel/saveChatSelections/savePickerSelections/setPrimaryChatModel/setById/selectEmbeddingModel/selectPendingTTSModel/saveTTSSelection/deleteModelForActiveSection + 派生 modelNamesForProvider/filteredModelNamesForProvider/selectedModelChipsForProvider/savedModelForActiveSection/isModelSelectedForActiveSection/activeModelStateLabel
- [ ] 入参透传 bundle + activeSection + sectionMeta + picker(pending/isSavingPicker/closeModelPicker) + mutations + loadBundle
- [ ] 验证：三件套 + wc + 手测三种能力选择/保存/删除

## Slice 9 — RoutingStagesPanel.vue 子组件

- [ ] 建子组件（含 AIMETA 首行）：迁 template L58-108 + 对应 scoped style
- [ ] props：routeSelections(v-model)/chatStageGroups/enabledChatModels/providerName/isSavingRoutes；emit update/save/navigate
- [ ] 父组件替换引用；scoped 迁移（父零残留 rg 验证）
- [ ] 验证：三件套 + wc + 手测 routes 分区

## Slice 10 — ProviderFormPanel.vue 子组件（合并 create/edit）

- [ ] 建子组件：合并 template L111-174（create）+ L210-275（edit），mode prop 区分
- [ ] props：providerForm(v-model)/mode/isSavingProvider；emit save/cancel
- [ ] scoped 迁移
- [ ] 验证：三件套 + wc + 手测 create/edit 表单

## Slice 11 — SelectedModelChips.vue + PrimaryModelPanel.vue

- [ ] 建 2 子组件（含 AIMETA）：L476-513 chips + L176-198 primary panel
- [ ] scoped 迁移
- [ ] 验证：三件套 + wc

## Slice 12 — ModelPickerDialog.vue 子组件（最高风险）

- [ ] 建子组件：迁 template L342-467（Teleport 弹窗）+ 全量 picker scoped style
- [ ] **保留 Teleport to body + fixed 定位 + id 选择器 + 函数 ref**
- [ ] props 大量透传（provider/activeSection/filteredModelNames/isLoading/isSavingPicker/pending sets/style/isChatPickerDirty/ref setters/state labels）；emit close/save/toggle-chat/select-embedding/select-tts
- [ ] onPickerClickOutside/onPickerViewportChange 监听归属（留父 document 级 或迁子 onMounted），行为等价验证
- [ ] 验证：三件套 + wc + 手测弹窗完整流程

## Slice 13-15 — style 余量收口 + <500 验收

- [ ] 剩余 scoped style 按区块迁子组件 / 页面级留父
- [ ] `wc -l` 跟踪至 <500
- [ ] 若 >500：评估是否过度抽象（template 真实大块已拆完则按收口原则说明）
- [ ] 全量手测清单跑一遍
- [ ] 更新 prd.md AC 勾选 + memory

## 收尾（每会话）

- 三件套绿 → 提交（commit message：`refactor(frontend): ...（#22 PersonalModelRouting Slice N）`）→ push
- design.md roadmap 表回填实测行数 + hash
- 跨会话：下个会话从 task.py current 继续，按 implement.md 未完成 slice 推进
- 全部完成 → `/trellis:finish-work` 归档

## 验证命令（每 slice 通用）

```bash
cd frontend && npx vue-tsc --noEmit
cd frontend && npx vitest run
cd frontend && npx eslint src/components/llm-settings/
cd frontend && wc -l src/components/llm-settings/PersonalModelRouting.vue
```
