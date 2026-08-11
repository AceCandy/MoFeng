# AIMETA P=小说模式_小说和章节请求响应|R=小说结构_章节结构|NR=不含业务逻辑|E=NovelSchema_ChapterSchema|X=internal|A=Pydantic模式|D=pydantic|S=none|RD=./README.ai
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChoiceOption(BaseModel):
    """前端选择项描述，用于动态 UI 控件。"""

    id: str
    label: str


class UIControl(BaseModel):
    """描述前端应渲染的组件类型与配置。"""

    type: str = Field(..., description="控件类型，如 single_choice/text_input")
    options: Optional[List[ChoiceOption]] = Field(default=None, description="可选项列表")
    placeholder: Optional[str] = Field(default=None, description="输入提示文案")


class ConverseResponse(BaseModel):
    """概念对话接口的统一返回体。"""

    ai_message: str
    ui_control: UIControl
    conversation_state: Dict[str, Any]
    is_complete: bool = False
    ready_for_blueprint: Optional[bool] = None


class ConverseRequest(BaseModel):
    """概念对话接口的请求体。"""

    user_input: Dict[str, Any]
    conversation_state: Dict[str, Any]


class ChapterGenerationStatus(str, Enum):
    NOT_GENERATED = "not_generated"
    GENERATING = "generating"
    EVALUATING = "evaluating"
    SELECTING = "selecting"
    FAILED = "failed"
    EVALUATION_FAILED = "evaluation_failed"
    WAITING_FOR_CONFIRM = "waiting_for_confirm"
    FINALIZING = "finalizing"
    SUCCESSFUL = "successful"


class ChapterOutline(BaseModel):
    chapter_number: int
    title: str
    summary: str
    goals: str = ""
    highlights: List[str] = Field(default_factory=list)
    character_states: Dict[str, str] = Field(default_factory=dict)


class ChapterGenerationTrace(BaseModel):
    id: int
    node_key: str
    node_label: str
    stage: Optional[str] = None
    status: str
    uses_llm: bool = False
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    raw_response: Optional[str] = None
    cleaned_output: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ChapterVersionSelection(BaseModel):
    """章节候选的公开选版投影，不暴露 provider payload 或内部结果 hash。"""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    content: str
    version_label: Optional[str] = Field(default=None, max_length=64)
    workflow_run_id: Optional[str] = Field(default=None, min_length=36, max_length=36)


class Chapter(ChapterOutline):
    real_summary: Optional[str] = None
    content: Optional[str] = None
    versions: Optional[List[str]] = None
    version_selections: Optional[List[ChapterVersionSelection]] = None
    evaluation: Optional[str] = None
    generation_status: ChapterGenerationStatus = ChapterGenerationStatus.NOT_GENERATED
    generation_progress: Optional[int] = None
    generation_step: Optional[str] = None
    generation_step_index: Optional[int] = None
    generation_step_total: Optional[int] = None
    generation_started_at: Optional[datetime] = None
    status_updated_at: Optional[datetime] = None
    word_count: Optional[int] = None
    generation_traces: List[ChapterGenerationTrace] = Field(default_factory=list)


class ConfirmFinalizeChapterRequest(BaseModel):
    selected_version_index: int = Field(..., ge=0)
    edited_content: Optional[str] = None
    skip_vector_update: bool = False


class ForeshadowingSyncStats(BaseModel):
    created: int = 0
    developing: int = 0
    revealed: int = 0


class ConfirmFinalizeStats(BaseModel):
    summary_generated: bool = False
    memory_updated: bool = False
    vector_ingested: bool = False
    foreshadowing_sync: ForeshadowingSyncStats = Field(default_factory=ForeshadowingSyncStats)


class ConfirmFinalizeChapterResponse(BaseModel):
    chapter: Chapter
    finalize: ConfirmFinalizeStats


class Relationship(BaseModel):
    character_from: str
    character_to: str
    description: str


class Blueprint(BaseModel):
    title: str
    target_audience: str = ""
    genre: str = ""
    style: str = ""
    tone: str = ""
    one_sentence_summary: str = ""
    full_synopsis: str = ""
    world_setting: Dict[str, Any] = {}
    characters: List[Dict[str, Any]] = []
    relationships: List[Relationship] = []
    chapter_outline: List[ChapterOutline] = []

    class Config:
        from_attributes = True


class NovelProject(BaseModel):
    id: str
    user_id: int
    title: str
    initial_prompt: str
    conversation_history: List[Dict[str, Any]] = []
    blueprint: Optional[Blueprint] = None
    chapters: List[Chapter] = []

    class Config:
        from_attributes = True


class NovelProjectSummary(BaseModel):
    id: str
    title: str
    genre: str
    last_edited: str
    completed_chapters: int
    total_chapters: int


class BlueprintGenerationResponse(BaseModel):
    blueprint: Blueprint
    ai_message: str


class ChapterGenerationResponse(BaseModel):
    ai_message: str
    chapter_versions: List[Dict[str, Any]]


class NovelSectionType(str, Enum):
    OVERVIEW = "overview"
    WORLD_SETTING = "world_setting"
    CHARACTERS = "characters"
    RELATIONSHIPS = "relationships"
    CHAPTER_OUTLINE = "chapter_outline"
    CHAPTERS = "chapters"


class NovelSectionResponse(BaseModel):
    section: NovelSectionType
    data: Dict[str, Any]


class GenerateChapterRequest(BaseModel):
    chapter_number: int
    writing_notes: Optional[str] = Field(default=None, description="章节额外写作指令")
    from_node_key: Optional[str] = Field(
        default=None, description="节点级恢复起点(trace node_key)，为空表示整章生成"
    )


class FlowConfig(BaseModel):
    preset: str = Field(default="basic", description="basic|enhanced|ultimate|custom")
    versions: Optional[int] = Field(default=None, description="生成版本数量")
    enable_preview: Optional[bool] = Field(default=None, description="是否启用预演生成")
    enable_optimizer: Optional[bool] = Field(default=None, description="是否启用优化器")
    enable_consistency: Optional[bool] = Field(default=None, description="是否启用一致性检查")
    enable_enrichment: Optional[bool] = Field(default=None, description="是否启用字数扩写")
    enable_rag: Optional[bool] = Field(default=None, description="是否启用 RAG")
    rag_mode: Optional[str] = Field(default=None, description="simple|two_stage")


class AdvancedGenerateRequest(BaseModel):
    project_id: str
    chapter_number: int
    writing_notes: Optional[str] = Field(default=None, description="章节额外写作指令")
    flow_config: FlowConfig = Field(default_factory=FlowConfig)
    from_node_key: Optional[str] = Field(
        default=None, description="节点级恢复起点(trace node_key)，为空表示整章生成"
    )


class AdvancedGenerateVariant(BaseModel):
    index: int
    version_id: int
    content: str
    metadata: Optional[Dict[str, Any]] = None


class AdvancedGenerateResponse(BaseModel):
    project_id: str
    chapter_number: int
    preset: str
    best_version_index: int
    variants: List[AdvancedGenerateVariant]
    review_summaries: Dict[str, Any] = Field(default_factory=dict)
    debug_metadata: Optional[Dict[str, Any]] = None


class FinalizeChapterRequest(BaseModel):
    project_id: str
    selected_version_id: int
    skip_vector_update: Optional[bool] = Field(default=False, description="是否跳过向量库更新")


class FinalizeChapterResponse(BaseModel):
    project_id: str
    chapter_number: int
    selected_version_id: int
    result: Dict[str, Any]


class SelectVersionRequest(BaseModel):
    chapter_number: int
    version_index: int


class EvaluateChapterRequest(BaseModel):
    chapter_number: int


class UpdateChapterOutlineRequest(BaseModel):
    chapter_number: int
    title: str
    summary: str
    goals: str = ""
    highlights: List[str] = Field(default_factory=list)
    character_states: Dict[str, str] = Field(default_factory=dict)


class DeleteChapterRequest(BaseModel):
    chapter_numbers: List[int]
    delete_artifacts_confirmed: bool = False
    confirmation_text: Optional[str] = None


class GenerateOutlineRequest(BaseModel):
    start_chapter: int = Field(..., ge=1)
    num_chapters: int = Field(..., ge=1, le=20)


class BlueprintPatch(BaseModel):
    one_sentence_summary: Optional[str] = None
    full_synopsis: Optional[str] = None
    world_setting: Optional[Dict[str, Any]] = None
    characters: Optional[List[Dict[str, Any]]] = None
    relationships: Optional[List[Relationship]] = None
    chapter_outline: Optional[List[ChapterOutline]] = None


class EditChapterRequest(BaseModel):
    chapter_number: int
    content: str
