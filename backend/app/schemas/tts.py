# AIMETA P=TTS请求模式_单段语音合成|R=文本长度校验|NR=不含模型配置|E=SpeechRequest|X=http|A=Pydantic模式|D=pydantic|S=none|RD=./README.ai
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2500)
    # 音色与倍速改为朗读时在控件选择（全局偏好），运行时覆盖模型默认值；缺省回退模型配置
    voice: Optional[str] = Field(default=None, max_length=64)
    speed: Optional[float] = Field(default=None, gt=0, le=4)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("朗读文本不能为空")
        return value
