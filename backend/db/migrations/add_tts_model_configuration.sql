-- 为用户模型补充 TTS 协议、默认音色、语速和默认模型标记。

ALTER TABLE user_ai_models ADD COLUMN is_default_tts BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE user_ai_models ADD COLUMN tts_protocol VARCHAR(32) NULL;
ALTER TABLE user_ai_models ADD COLUMN tts_voice VARCHAR(120) NULL;
ALTER TABLE user_ai_models ADD COLUMN tts_speed FLOAT NOT NULL DEFAULT 1.0;
