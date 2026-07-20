# P3 小项治理 - 实施

## 前置确认（实现前 rg）
- [ ] #8 analytics.py 复制函数是否在用（emotion_analyzer.py 已 P1 删，analytics 本地函数是否唯一来源 -> 决策）
- [ ] #14 novel store currentConversationState 外部引用（rg）
- [ ] #6 ProjectMemory.version 现状（rg version 自增点）
- [ ] #5 memory_layer 4 表时间戳现状

## 实施顺序

### Commit 1: 后端时间戳规范化（#5/#19）
- [ ] memory_layer.py 4 表 created_at/updated_at：nullable=False + server_default=func.now()；updated_at onupdate=func.now()
- [ ] foreshadowing_service.py datetime.utcnow -> datetime.now(timezone.utc)
- [ ] 验证 pytest

### Commit 2: 乐观锁 + seq 并发（#6/#18）
- [ ] ProjectMemory update 加 WHERE version=? 守卫，冲突抛异常
- [ ] novel_service.append_conversation seq 改原子（INSERT SELECT MAX+1 或唯一约束）
- [ ] 补测试（乐观锁冲突 + seq 并发）
- [ ] 验证 pytest

### Commit 3: 死代码删除（#1/#9/#14）
- [ ] backend updates.py /remote-version 路由删（P1 已删 frontend 链路，死路由+未鉴权+SSRF）
- [ ] character_dna_guide.md：init_db 灌入删除 + DB 清理迁移
- [ ] novel store currentConversationState/resetConversationState 删（确认无外部引用）
- [ ] 验证 pytest + 前端四件套

### Commit 4: 前端监听泄漏（#15）
- [ ] AppShell.vue onMounted matchMedia 监听，onUnmounted 移除
- [ ] 验证前端四件套

### Commit 5: 参数去重（#4）
- [ ] optimizer apply_optimization optimized_content 只从 body，去 query 参数
- [ ] 验证 pytest

## 决策项
- #7 debug 默认 True：保留（开发友好，P2 K 强制生产关闭）
- #8 情感分析分叉：emotion_analyzer.py 已 P1 删，analytics.py 本地函数是唯一来源，无分叉，不修（待确认）

## 全量验证
- [ ] 后端 pytest 全绿
- [ ] 前端四件套全绿
- [ ] 独立复核
