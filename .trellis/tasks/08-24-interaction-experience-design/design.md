# 整体创作交互体验技术设计

## 1. 交互方向

采用“续写签”而不是全局向导：复用 AppShell 已有项目胶囊、项目进度和档案/写作入口，只补齐当前阶段与最近语义位置。用户每次看到一个主动作，次要动作负责返回、查看档案或退出。

页面状态与动作如下：

| 页面/状态 | 唯一主动作 | 次要动作 | 离开与恢复 |
| --- | --- | --- | --- |
| 工作台·无项目 | 开始新灵感 | 导入已有作品 | 新建灵感项目 |
| 工作台·有上下文 | 继续灵感/查看档案/继续第 N 章 | 新建灵感 | 按最近服务端上下文进入 |
| 灵感·对话中 | 发送当前回答 | 重开、退出 | 已发送对话照旧持久化；未发送草稿按轮次同步 |
| 蓝图·生成前 | 开始创建蓝图 | 返回继续补充 | 返回不丢已发送对话与当前有效草稿 |
| 蓝图·展示 | 确认并开始创作 | 重新生成 | 保存成功进入第一章写作台 |
| 项目档案 | 继续创作 | 返回工作台、编辑档案 | 恢复最近章节而非固定第一章 |
| 写作台·各工作流态 | 复用状态机给出的启动/选版/重试/定稿动作 | 档案、章节、版本与评审 | 恢复章节与可用分区 |
| 后台任务·运行/成功/失败 | 返回创作/查看结果/回去处理 | 展开日志 | 离开不取消；失败处理回到写作台 |

AppShell 对 `inspiration`、`project-detail`、`project-write` 统一展示项目身份，并显示“灵感采集 / 项目档案 / 第 N 章写作”阶段签。阶段签只在阶段真的变化时做一次短促进入反馈。

## 2. 服务端上下文合同

### 2.1 数据模型

新增 `user_creation_contexts`，以 `(user_id, project_id)` 为复合主键：

- `user_id`：外键 `users.id`，级联删除；
- `project_id`：外键 `novel_projects.id`，级联删除；
- `surface`：`inspiration | archive | writing`；
- `chapter_number`：可空正整数；
- `desk_section`：可空 `content | versions | evaluation`；
- `inspiration_draft`：可空文本；
- `inspiration_turn`：可空非负整数，用于阻止旧轮次草稿错位恢复；
- `updated_at`：数据库时间，作为最近项目排序与最后写入事实。

不增加版本号和冲突表。记录按项目隔离，避免设备在不同项目上的操作互相覆盖；普通字段及同一灵感轮次内的草稿由最后一次数据库提交覆盖。

### 2.2 API

- `GET /api/creation-contexts`：返回当前用户全部上下文，按 `updated_at DESC, project_id ASC`；工作台取第一条，项目页从同一 Vue Query 缓存查找自己的记录。
- `PATCH /api/creation-contexts/{project_id}`：只更新请求中出现的字段；服务先校验项目归属，再以 PostgreSQL upsert 原子写入。

PATCH 而非整对象 PUT，避免只修改草稿时用陈旧章节/分区覆盖其他设备的新值。字段级最后写入仍不检测版本、不返回 409。空 PATCH 拒绝；枚举、章节号和轮次在 Pydantic 与数据库约束两侧校验。

草稿 PATCH 必须同时携带 `inspiration_turn`。服务端以项目已持久化对话中的 assistant 轮数为权威轮次：

- 请求轮次等于权威轮次：按最后数据库提交覆盖该轮草稿；
- 请求轮次小于权威轮次：不写入旧草稿，原子清空上下文中的过期草稿并推进记录轮次，返回当前上下文，不返回 409；
- 请求轮次大于权威轮次：按无效输入拒绝，避免客户端凭空推进对话事实。

因此“最后写入覆盖”只作用于同一逻辑草稿；对话已经推进后，旧轮次写入不再是同一个可覆盖字段。前端收到服务端更高轮次时清除本机过期备份，不显示冲突界面。

### 2.3 迁移与兼容

- 新表为空时所有页面保持当前行为：工作台回退 `last_edited`，写作台回退 query/首章与 `content`，灵感草稿为空。
- 删除项目或用户时级联删除上下文。
- downgrade 只删除新表，不改变项目、章节、对话和任务数据。

## 3. 前端数据流

### 3.1 所有权

- 服务端上下文进入 TanStack Vue Query；不镜像到 Pinia。
- route query 仍是写作台当前章节的可分享导航事实；服务端上下文负责缺省恢复，并在用户切章后更新。
- 组件内瞬时状态继续留在本地 `ref`；只把 PRD 明确列出的语义字段提交服务端。

### 3.2 恢复顺序

1. 路由鉴权守卫恢复用户；
2. 项目与 creation contexts 并行查询；
3. 显式路由参数优先，服务端上下文其次，既有默认值最后；
4. 恢复值必须通过当前项目事实校验：章节存在、分区在当前章节可用、草稿轮次等于已恢复对话轮次；
5. 无效值回退，不把回退值误报为远端冲突。

优先级保证任务结果的显式章节链接、用户手动输入 URL 和浏览器历史不会被旧上下文反向覆盖。

contexts query 在页面进入与窗口重新聚焦时刷新。重新聚焦只把远端值应用到未被本机修改的字段；正在编辑的本地草稿或当前章节不被突然替换，它们下一次成功 PATCH 后按最后写入成为服务端事实。刷新/重新进入始终从服务端重新水合。

### 3.3 保存时机

- 进入灵感、档案、写作台时更新 `surface`；
- 写作台选章与切分区时分别 PATCH 对应字段；
- 灵感输入同步写入用户+项目隔离、带 `saved_at` 的临时本地备份，并短防抖 PATCH `inspiration_draft + inspiration_turn`；blur/路由离开时尝试 flush；
- 服务端成功后移除本地备份；网络失败保留并显示“已保存在本机，联网后同步”，下次进入或重新联网时重试；备份最多保留 24 小时，应用启动时清理过期项，账号身份变化或退出时清除上一用户的未同步备份；
- 发送成功或灵感轮次推进后，PATCH 清空草稿并写入新轮次。

本地备份不参与跨设备比较：它只有“未成功提交”或“已提交并删除”两态。若同轮次离线备份后来成功提交，它自然成为服务端最后写入；若权威轮次已推进，服务端静默丢弃它。备份在浏览器内是明文，仅用于短期故障保护，不写入日志、测试夹具或仓库。

### 3.4 组件接线

- `ConversationInput` 增加标准 `v-model` 草稿合同；控件身份变化仍清空不匹配草稿，但父层可在对话恢复完成后注入同轮次远端值。
- `WDWorkspace` 增加受控分区值/变更事件；切章时若恢复分区不可用则回 `content`。
- `NovelWorkspace` 的继续动作优先使用最近上下文；项目卡标题修正为项目档案入口。
- `NovelDetailShell` 的继续创作使用上下文章节；`WritingDesk` 切章时继续维护 `chapter_number` query，保证 URL 与服务端上下文一致。
- AppShell 从 inspiration query 解析项目 id，并展示阶段签；不新增第二套项目选择器。

## 4. 后台任务结果回跳

继续复用现有任务列表、snapshot、SSE 和详情接口。`BackgroundTaskResponse` 新增可空 `chapter_number`，由 `job_public_projection` 仅对 `chapter_workflow`、`chapter_finalize`、`chapter_edit_postprocess` 三种可回到正文的任务，从已验证 payload 的正整数 `chapter_number` 字段生成；不公开 payload，不从日志/标题解析，不提高 SSE schema version。

前端以明确白名单映射：

- `chapter_workflow`、`chapter_finalize`、`chapter_edit_postprocess`：有章节号时进入 `/projects/:id/write?chapter_number=N`；无章节号时退回项目写作台；
- `chapter_outline`：进入项目档案，查看更新后的章节大纲；
- `chapter_projection_memory`、`chapter_projection_rag`、`chapter_projection_foreshadowing`、`chapter_projection_trace`：进入项目档案，不公开或使用章节号；
- `chapter_outbox_dispatch`、`chapter_projection_reconcile`、`chapter_projection_tombstone`：内部治理任务只展示日志，不显示导航动作；
- 无 `project_id`：不展示导航动作。

失败 workflow 只显示“回去处理”，进入写作台后由现有 workflow snapshot 的 `allowed_commands` 决定重试、重同步、取消或重置。任务面板不新增通用 retry/cancel API。

## 5. 状态、无障碍与动效

- 上下文查询失败不阻断创作，只回退现有默认行为并提供一次非阻塞重试反馈。
- 草稿同步状态用文字和 `aria-live=polite` 表达；颜色不是唯一信号。
- 新增动作使用原生 button/link，保持 44px 触控目标、可见焦点与正确禁用态。
- “阶段签轻落”只使用 opacity/transform，单次短时播放；`prefers-reduced-motion: reduce` 下移除过渡并直接显示终态。
- 任务跳转关闭面板后导航，返回时焦点由现有 dialog/AppShell 合同恢复。

## 6. 关键取舍

- 选择字段级 PATCH + 数据库 upsert，而不是整对象 PUT，避免无关字段被陈旧快照覆盖。
- 选择请求时同步 + 聚焦/重新进入刷新，而不是 WebSocket 草稿广播；需求是跨设备恢复，不是实时协同。
- 选择专用上下文表，而不是把 UI 状态塞入 `NovelProject` 或 `ProjectMemory`，保持项目内容、AI 记忆与用户工作位置边界清晰。
- 选择公开一个严格白名单章节号，而不是暴露任务 payload 或复制一套通用任务命令系统。

## 7. 回滚

- 前端可先回退到现有 `last_edited`、route query 和组件默认值；新 API 失败时也按此降级。
- 后端路由、模型与迁移可独立回滚；上下文表不承载项目正文，删除不会损伤创作内容。
- 任务 `chapter_number` 为可空兼容字段，旧事件与旧客户端均可继续工作。
