# 墨风前端技术质量审计报告 (第一版)

## 审计健康评分 (Audit Health Score)

| # | 维度 | 评分 | 核心发现 |
|---|-----------|-------|-------------|
| 1 | 无障碍性 (Accessibility) | 2/4 | 移动端多处交互按钮（Checkbox、Toggle、删除）触控热区小于 44px，部分纯图标按钮缺少 `aria-label` 描述。 |
| 2 | 性能 (Performance) | 3/4 | 整体渲染性能良好，无严重的渲染抖动与阻塞。 |
| 3 | 响应式设计 (Responsive) | 2/4 | `.model-routing__provider-grid` 中强制的最小 400px 宽度卡片在 375px 小屏下导致横向滚动条溢出。 |
| 4 | 主题化 (Theming) | 2/4 | 存在裸硬编码颜色（如 `#C0392B`），以及多处多余的变量 fallback 颜色硬编码。 |
| 5 | 反模式 (Anti-Patterns) | 3/4 | 整体符合古典中国风的设计，但有部分大圆角使用（偏离“方正木刻”原则），且小屏下 Tab 高度过高。 |
| **总分** | | **12/20** | **可接受 (Acceptable)** |

---

## 反模式诊断 (Anti-Patterns Verdict)
- **结论**：**通过**。项目整体没有使用霓虹发光文字、紫蓝 SaaS 渐变背景或现代弥散阴影等违背“徽墨熟宣、朱砂印鉴”中国风的主流反模式。
- **具体AI痕迹/反模式细节**：
  - 细节1：`PersonalModelRouting.vue` 中使用了大圆角 `border-radius: var(--md-radius-lg)`，虽然使用了 token，但偏离了项目“刀刻折页的方正感”原则。
  - 细节2：移动端 Tab 高度仍保留了 64px 配合小屏较小的屏幕空间，容易产生窒息感。

---

## 缺陷明细与修复指南 (Detailed Findings)

### 1. 无障碍维度 (Accessibility)

#### [P1] 移动端交互按钮触控热区过小
- **位置**：[PersonalModelRouting.vue](file:///d:/%E6%96%87%E6%A1%A3/%E4%B8%B4%E6%97%B6workspace/MoFeng/frontend/src/components/llm-settings/PersonalModelRouting.vue#L1967) (包括 Checkbox、Toggle 开关 `.model-routing__toggle` 和删除按钮 `.model-routing__delete-btn` 等)
- **影响**：Checkbox 尺寸为 20x20px，开关高度为 28px，均不符合移动端触控热区要求，导致指尖点击极易失败。
- **标准违背**：WCAG 2.1 AA 2.5.5 Target Size (Minimum 44x44px)
- **修复方案**：通过增加 padding，或利用 `::before` 伪元素向外扩张其点击感应范围，使其实际可交互尺寸满足最少 44x44px 的规范，同时保持视觉尺寸不变。
- **推荐指令**：`$impeccable layout`

#### [P2] 纯图标按钮缺少辅助提示文本
- **位置**：[PersonalModelRouting.vue](file:///d:/%E6%96%87%E6%A1%A3/%E4%B8%B4%E6%97%B6workspace/MoFeng/frontend/src/components/llm-settings/PersonalModelRouting.vue#L1840) 等纯 SVG 图标删除按钮处
- **影响**：视障用户使用读屏软件时，无法获知该按钮的业务操作意图。
- **修复方案**：在 `<button>` 元素上添加 `aria-label="删除此模型"` 或 `aria-label="删除此供应商"`，提供必要的语义解说。
- **推荐指令**：`$impeccable harden`

---

### 2. 响应式设计维度 (Responsive)

#### [P1] 移动视口小屏下出现布局横向溢出 (滚动条)
- **位置**：[PersonalModelRouting.vue](file:///d:/%E6%96%87%E6%A1%A3/%E4%B8%B4%E6%97%B6workspace/MoFeng/frontend/src/components/llm-settings/PersonalModelRouting.vue#L1538) 中的 `.model-routing__provider-grid` 样式
- **影响**：样式原设为 `grid-template-columns: repeat(auto-fit, minmax(400px, 1fr))`。在 375px 的手机视口下，卡片宽度被锁定在最少 400px，导致卡片超出容器边界，产生横向溢出并出现丑陋的滚动条。
- **修复方案**：将 `minmax(400px, 1fr)` 升级为安全自适应模式 `minmax(min(100%, 400px), 1fr)`，确保卡片宽度可以随着小屏幕收缩。
- **推荐指令**：`$impeccable adapt`

#### [P2] 移动端下 Tab 导航层级空间拥挤
- **位置**：[SettingsView.vue](file:///d:/%E6%96%87%E6%A1%A3/%E4%B8%B4%E6%97%B6workspace/MoFeng/frontend/src/views/SettingsView.vue#L708) 处的移动端媒体查询样式
- **影响**：小屏下 Tab 排列从一列被压缩为多列，每个 Tab 的高度为 64px 且字体字号大，霸占了手机首屏的大部分垂向空间，阻碍了内容区主界面的初次呈现。
- **修复方案**：在媒体查询中，适当降低移动端 Tab 的最小高度（例如由 64px 缩减至 48px），微调内边距并减小文字与副标题的大小。
- **推荐指令**：`$impeccable layout`

---

### 3. 主题与 Token 维度 (Theming)

#### [P1] 存在裸硬编码颜色值
- **位置**：[PersonalModelRouting.vue](file:///d:/%E6%96%87%E6%A1%A3/%E4%B8%B4%E6%97%B6workspace/MoFeng/frontend/src/components/llm-settings/PersonalModelRouting.vue#L2157)
- **影响**：在 `.md-btn-tonal:hover:not(:disabled)` 中硬编码了 `background: #C0392B !important;`。若系统今后统一调改警告或按钮色调，该 hover 态将保持旧红，且无法跟随亮暗色调主题联动。
- **修复方案**：改用系统内置变量 `var(--md-error-strong)` 或在 `main.css` 中声明的按钮色。
- **推荐指令**：`$impeccable colorize`

#### [P2] 冗余的硬编码 CSS 变量 Fallback 颜色
- **位置**：[PersonalModelRouting.vue](file:///d:/%E6%96%87%E6%A1%A3/%E4%B8%B4%E6%97%B6workspace/MoFeng/frontend/src/components/llm-settings/PersonalModelRouting.vue#L1784) 及其多处变量声明
- **影响**：使用了如 `var(--md-secondary, #B83C32)` 这样的 fallback，使得变量的颜色值重复散落在各个页面和组件内，不便进行全局维护与一键换色。
- **修复方案**：直接简化为变量的单一引用 `var(--md-secondary)`，依赖 `main.css` 中的集中初始化定义来保证 fallback。
- **推荐指令**：`$impeccable document`

---

### 4. 偏离设计规范 (Anti-Patterns)

#### [P2] 容器使用大圆角样式
- **位置**：[PersonalModelRouting.vue](file:///d:/%E6%96%87%E6%A1%A3/%E4%B8%B4%E6%97%B6workspace/MoFeng/frontend/src/components/llm-settings/PersonalModelRouting.vue#L1494) 样式 `.model-routing__panel`
- **影响**：设置了 `border-radius: var(--md-radius-lg);` (12px)。违反了墨风设计体系中对于方正利落、直圆角的木刻风骨要求。
- **修复方案**：将其圆角缩窄，改用符合规范的微直角 `border-radius: var(--md-radius-xs);` 或 `var(--md-radius-sm)` (2px-6px)。
- **推荐指令**：`$impeccable quieter`

---

## 推荐指令与修复优先级 (Recommended Actions)

按优先级排列：

1. **[P1] `$impeccable adapt`**：修复 `PersonalModelRouting.vue` 在移动端（375px）小屏下的横向滚动条溢出。
2. **[P1] `$impeccable layout`**：为无障碍微调 checkbox 与 toggle 点击热区到至少 44px 高宽。
3. **[P1] `$impeccable colorize`**：消除 `PersonalModelRouting.vue` 第 2157 行的硬编码颜色 `#C0392B`。
4. **[P2] `$impeccable layout`**：修改移动端（小视口）的 Tab 导航，减少高宽与行高占比。
5. **[P2] `$impeccable quieter`**：移除 `.model-routing__panel` 处的 12px 大圆角，改为 2px/4px 极窄直角。
6. **[P2] `$impeccable harden`**：在删除、编辑等纯 SVG 图标按钮上增配 `aria-label`。
7. **[P2] `$impeccable document`**：清理 CSS 代码里硬编码的变量 Fallbacks 颜色。
8. **[P3] `$impeccable polish`**：对整体修复后的界面细节进行最后一轮审查。

> 您可以要求我逐个运行这些推荐指令，或按照您的偏好顺序执行。
>
> 修复完成后重新运行 `$impeccable audit` 可查看健康评分的改善。
