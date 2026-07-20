# P3 小项治理 - 设计

## 范围

审计 low 19 项。分类处置：
- **P1 已处理 7 项**：#2/#10/#11/#12/#13/#16/#17（dead-code 类）
- **P2 已处理 1 项**：#3 assert_production_security debug 校验
- **P3 真做 10 项**：#1/#4/#5/#6/#8/#9/#15/#18/#19 + #14(确认后删)
- **决策 1 项**：#7 debug 默认 True（开发友好保留，P2 K 已强制生产关闭）

## 修复模式

### 后端时间戳规范化（#5/#19）
- memory_layer 4 表（CharacterState/CharacterRelationship/FactionState/FactionRelationshipHistory 等）created_at/updated_at：nullable=False + server_default=func.now()；updated_at 加 onupdate=func.now()
- foreshadowing_service.py 多处 datetime.utcnow() -> datetime.now(timezone.utc)
- 不改模型默认值的语义，只补 server_default + timezone

### 乐观锁（#6）
- ProjectMemory.version：UPDATE 时加 WHERE version=? 守卫，冲突抛异常或重试。现状只自增无守卫。
- 修法：update 语句 `WHERE id=? AND version=?`，affected_rows=0 则抛 ConcurrentUpdateError。

### seq 并发（#18）
- novel_service.append_conversation 用 select(max(seq))+1，并发重复。
- 修法：PG `INSERT ... SELECT COALESCE(MAX(seq),0)+1 FROM novel_conversations WHERE project_id=?`（一条 SQL 原子），或加唯一约束 project_id+seq 兜底。

### 监听泄漏（#15）
- frontend AppShell.vue onMounted 注册 matchMedia('change') 监听，onUnmounted 未移除。
- 修法：onMounted 存 mql + listener，onUnmounted mql.removeListener 或 mql.removeEventListener。

### 死代码删除（#1/#9/#14）
- #1 backend /api/updates/remote-version 路由：P1 已删 frontend 链路，backend 路由死 + 未鉴权+SSRF。删路由 + 相关函数。
- #9 character_dna_guide.md：init_db 灌入 DB 但无 get_prompt 引用。删 init_db 灌入 + DB 清理（迁移或脚本）。
- #14 novel store currentConversationState/resetConversationState：确认无外部访问则删。

### 参数去重（#4）
- optimizer apply_optimization 同时接受 body + query optimized_content。修法：optimized_content 只从 body，去掉 query 参数。

### 情感分析分叉（#8）
- analytics.py 本地复制 emotion_analyzer 函数，两份关键词表分叉。修法：analytics.py 复用 utils/emotion_analyzer.py（若 P1 未删）或统一到一处。需确认 emotion_analyzer 是否 P1 已删（P1 删 EmotionService + emotion_analyzer.py）。若已删，analytics.py 的复制函数也删或保留单一来源。

## 决策项

- #7 debug 默认 True：开发友好（本地调试），生产用 assert_production_security 强制关闭（P2 K 已修）。保留默认 True，不改。

## 验证
- 后端 pytest 全绿 + 前端四件套全绿
- 行为变更补测试（乐观锁冲突、seq 并发）
- 独立复核

## 提交拆分
1. 后端时间戳规范化（#5/#19）
2. 乐观锁 + seq 并发（#6/#18）
3. 死代码删除（#1/#9/#14）
4. 前端监听泄漏（#15）
5. 参数去重 + 情感分析分叉（#4/#8）
