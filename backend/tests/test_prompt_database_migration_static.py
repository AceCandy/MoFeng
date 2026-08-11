from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
FRONTEND_SRC = PROJECT_ROOT / "frontend" / "src"
PROMPTS_ROOT = BACKEND_ROOT / "prompts"


def _backend_source(path: str) -> str:
    return (BACKEND_ROOT / path).read_text(encoding="utf-8")


def _frontend_source(path: str) -> str:
    return (FRONTEND_SRC / path).read_text(encoding="utf-8")


MIGRATED_PROMPTS = {
    "blueprint_json_repair": "JSON 语法修复器",
    "chapter_enrichment": "补写扩展",
    "chapter_compression": "删减压缩",
    "foreshadowing_candidate_review": "伏笔候选",
    "foreshadowing_status_judge": "历史伏笔",
    "emotion_analysis": "情感走向",
    "chapter_preview_generate": "章节预览",
    "chapter_preview_evaluate": "预览质量",
    "chapter_preview_expand": "扩写成完整章节",
    "import_character_filter": "角色鉴别",
    "optimize_recommended_version": "推荐版本优化",
}


def test_migrated_inline_prompts_exist_as_default_prompt_files():
    missing = []
    empty = []
    for prompt_name, required_text in MIGRATED_PROMPTS.items():
        path = PROMPTS_ROOT / f"{prompt_name}.md"
        if not path.is_file():
            missing.append(prompt_name)
            continue
        content = path.read_text(encoding="utf-8")
        if required_text not in content:
            empty.append(prompt_name)

    assert missing == []
    assert empty == []


def test_migrated_prompt_text_is_not_kept_as_code_fallbacks():
    checks = {
        "app/api/routers/novels.py": [
            "BLUEPRINT_JSON_REPAIR_PROMPT",
            "你是 JSON 语法修复器",
        ],
        "app/api/routers/optimizer.py": [
            "DEFAULT_RECOMMENDED_VERSION_PROMPT",
            "DEFAULT_RHYTHM_PROMPT",
            "小说推荐版本优化专家",
        ],
        "app/api/routers/writer.py": [
            "请在不改变主线剧情与关键事件的前提下",
            "请把下面小说章节压缩到约",
            "你是长篇小说伏笔编辑，只保留真正有后续叙事价值的伏笔",
            "你是长篇小说伏笔编辑，判断本章是否真正推进或回收历史伏笔",
        ],
        "app/api/routers/analytics.py": [
            "请分析以下小说章节的情感走向",
            "你是一个专业的小说情感分析师。",
        ],
        "app/services/preview_generation_service.py": [
            "现在需要为第 {chapter_number} 章生成一个简短的",
            "评估以下章节预览的质量",
            "现在需要将章节预览扩写成完整的章节正文",
        ],
        "app/services/import_service.py": [
            "你是一个严谨的网文角色鉴别师",
        ],
    }

    offenders = []
    for path, forbidden_texts in checks.items():
        source = _backend_source(path)
        for forbidden_text in forbidden_texts:
            if forbidden_text in source:
                offenders.append(f"{path}: {forbidden_text}")

    assert offenders == []


def test_prompt_usage_map_points_migrated_stages_to_database_prompts():
    source = _frontend_source("constants/promptUsage.ts")

    expected_prompt_names = [
        "blueprint_json_repair",
        "chapter_enrichment",
        "chapter_compression",
        "foreshadowing_candidate_review",
        "foreshadowing_status_judge",
        "emotion_analysis",
        "chapter_preview_generate",
        "chapter_preview_evaluate",
        "chapter_preview_expand",
        "import_character_filter",
        "optimize_recommended_version",
    ]

    for prompt_name in expected_prompt_names:
        assert prompt_name in source

    for inline_id in [
        "chapter-enrichment",
        "chapter-compression",
        "foreshadowing",
        "emotion-analysis",
        "chapter-preview",
    ]:
        block = source.split(f"id: '{inline_id}'", 1)[1].split("},", 1)[0]
        assert "status: 'inline'" not in block
        assert "promptNames: []" not in block
