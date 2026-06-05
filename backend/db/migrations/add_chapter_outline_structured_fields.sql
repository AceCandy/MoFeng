-- 迁移脚本：给 chapter_outlines 表添加章节目标、看点列表和角色瞬时状态
-- 项目未上线，按最新结构直接新增必填列，不做旧数据兜底。

ALTER TABLE chapter_outlines ADD COLUMN goals TEXT NOT NULL;
ALTER TABLE chapter_outlines ADD COLUMN highlights JSON NOT NULL;
ALTER TABLE chapter_outlines ADD COLUMN character_states JSON NOT NULL;
