from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_core_user_facing_ai_calls_pass_stage_keys():
    checks = {
        "app/api/routers/novels.py": [
            'stage="concept_conversation"',
            'stage="world_blueprint"',
        ],
        "app/api/routers/writer.py": [
            'stage="chapter_outline"',
            'stage="chapter_mission"',
            'stage="chapter_writing"',
            'stage="chapter_rewrite"',
            'stage="chapter_compression"',
            'stage="summary_memory"',
        ],
        "app/api/routers/optimizer.py": [
            'stage="chapter_optimization"',
        ],
        "app/api/routers/analytics.py": [
            'stage="emotion_analysis"',
        ],
        "app/services/ai_review_service.py": [
            'stage="version_review"',
        ],
        "app/services/import_service.py": [
            'stage="import_analysis"',
        ],
        "app/services/preview_generation_service.py": [
            'stage="chapter_preview"',
        ],
    }

    for path, needles in checks.items():
        source = _source(path)
        for needle in needles:
            assert needle in source, f"{needle} missing from {path}"


def test_embedding_calls_pass_rag_embedding_stage():
    checks = [
        "app/services/chapter_ingest_service.py",
        "app/services/chapter_context_service.py",
        "app/services/knowledge_retrieval_service.py",
    ]

    for path in checks:
        source = _source(path)
        assert 'stage="rag_embedding"' in source
