# AIMETA P=模型包初始化_导出所有模型类|R=包标识_模型导出|NR=不含模型实现|E=-|X=internal|A=-|D=none|S=none|RD=./README.ai
"""集中导出 ORM 模型，确保 SQLAlchemy 元数据在初始化时被正确加载。"""

from .admin_setting import AdminSetting
from .ai_model_config import UserAIModel, UserAIStageRoute, UserModelProvider
from .background_task import BackgroundTask
from .llm_config import LLMConfig
from .novel import (
    BlueprintCharacter,
    BlueprintRelationship,
    Chapter,
    ChapterEvaluation,
    ChapterOutline,
    ChapterVersion,
    NovelBlueprint,
    NovelConversation,
    NovelProject,
)
from .prompt import Prompt
from .update_log import UpdateLog
from .usage_metric import UsageMetric
from .user import User
from .system_config import SystemConfig

# 新增：项目记忆模型
from .project_memory import ProjectMemory, ChapterSnapshot

# 新增：章节蓝图模型
from .chapter_blueprint import (
    ChapterBlueprint,
    BlueprintTemplate,
    SuspenseDensity,
    ForeshadowingOp,
    ChapterFunction,
)
from .chapter_generation_trace import ChapterGenerationTrace

# 新增：记忆层模型
from .memory_layer import (
    CharacterState,
    CharacterStateType,
    TimelineEvent,
    CausalChain,
    StoryTimeTracker,
)

# 新增：伏笔模型
from .foreshadowing import (
    Foreshadowing,
    ForeshadowingResolution,
    ForeshadowingReminder,
    ForeshadowingStatusHistory,
    ForeshadowingAnalysis,
)

# 新增：势力/宪法/Writer人格模型
from .faction import (
    Faction,
    FactionRelationship,
    FactionMember,
    FactionRelationshipHistory,
)
from .constitution import NovelConstitution
from .writer_persona import WriterPersona

# RAG 向量检索模型（pgvector）
from .rag import RagChunk, RagSummary

__all__ = [
    # 基础模型
    "AdminSetting",
    "BackgroundTask",
    "UserModelProvider",
    "UserAIModel",
    "UserAIStageRoute",
    "LLMConfig",
    "NovelConversation",
    "NovelBlueprint",
    "BlueprintCharacter",
    "BlueprintRelationship",
    "ChapterOutline",
    "Chapter",
    "ChapterVersion",
    "ChapterEvaluation",
    "ChapterGenerationTrace",
    "NovelProject",
    "Prompt",
    "UpdateLog",
    "UsageMetric",
    "User",
    "SystemConfig",
    # 项目记忆模型
    "ProjectMemory",
    "ChapterSnapshot",
    # 章节蓝图模型
    "ChapterBlueprint",
    "BlueprintTemplate",
    "SuspenseDensity",
    "ForeshadowingOp",
    "ChapterFunction",
    # 记忆层模型
    "CharacterState",
    "CharacterStateType",
    "TimelineEvent",
    "CausalChain",
    "StoryTimeTracker",
    # 伏笔模型
    "Foreshadowing",
    "ForeshadowingResolution",
    "ForeshadowingReminder",
    "ForeshadowingStatusHistory",
    "ForeshadowingAnalysis",
    # 势力/宪法/Writer人格模型
    "Faction",
    "FactionRelationship",
    "FactionMember",
    "FactionRelationshipHistory",
    "NovelConstitution",
    "WriterPersona",
    # RAG 向量检索模型
    "RagChunk",
    "RagSummary",
]
