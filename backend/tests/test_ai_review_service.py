import json

from app.services.ai_review_service import AIReviewService, VersionReview


def test_parse_review_response_uses_one_based_version_numbers() -> None:
    service = AIReviewService(llm_service=None, prompt_service=None)
    response = json.dumps(
        {
            "best_version_number": 2,
            "overall_evaluation": "版本2更稳",
            "final_recommendation": "选择版本2",
            "version_reviews": [
                {
                    "version_number": 1,
                    "pros": ["铺垫清晰"],
                    "cons": ["节奏偏慢"],
                    "overall_review": "版本1较稳但不够有力",
                    "scores": {"coherence": 78},
                },
                {
                    "version_number": 2,
                    "pros": ["情绪推进更强"],
                    "cons": ["个别句子略满"],
                    "overall_review": "版本2综合最佳",
                    "scores": {"coherence": 86},
                },
            ],
        },
        ensure_ascii=False,
    )

    result = service._parse_review_response(response, ["a", "b"])

    assert result.best_version_index == 1
    assert [review.version_number for review in result.version_reviews] == [1, 2]
    assert result.version_reviews[1].overall_review == "版本2综合最佳"
    assert result.scores == {"coherence": 86}


def test_to_evaluation_payload_preserves_version_specific_reviews() -> None:
    payload = AIReviewService(llm_service=None, prompt_service=None)._build_fallback_result(
        "兜底", ["版本A", "版本B"]
    )
    payload.version_reviews = [
        VersionReview(
            version_number=1,
            pros=["版本1优点"],
            cons=["版本1缺点"],
            overall_review="仅讨论版本1",
            scores={"style": 80},
        ),
        VersionReview(
            version_number=2,
            pros=["版本2优点"],
            cons=["版本2缺点"],
            overall_review="仅讨论版本2",
            scores={"style": 88},
        ),
    ]
    payload.best_version_index = 1
    payload.final_recommendation = "选择版本2"

    evaluation_payload = payload.to_evaluation_payload()

    assert evaluation_payload["best_choice"] == 2
    assert evaluation_payload["reason_for_choice"] == "选择版本2"
    assert evaluation_payload["evaluation"]["version1"]["overall_review"] == "仅讨论版本1"
    assert evaluation_payload["evaluation"]["version2"]["overall_review"] == "仅讨论版本2"


def test_parse_review_response_falls_back_for_invalid_json() -> None:
    service = AIReviewService(llm_service=None, prompt_service=None)

    result = service._parse_review_response("not-json", ["a", "b"])

    assert result.best_version_index == 0
    assert result.final_recommendation == "解析失败，建议人工审核"
    assert [review.version_number for review in result.version_reviews] == [1, 2]
    assert all(
        review.overall_review == "AI 返回非结构化结果，建议人工复核"
        for review in result.version_reviews
    )


def test_build_base_context_payload_includes_review_context_extensions() -> None:
    service = AIReviewService(llm_service=None, prompt_service=None)

    payload = service._build_base_context_payload(
        {
            "pending_foreshadows": [{"id": 1, "content": "旧伏笔"}],
            "related_chapters": [{"chapter_number": 2, "summary": "前文摘要"}],
            "active_plot_threads": [{"thread_name": "寻找真相"}],
        }
    )

    assert payload["pending_foreshadows"] == [{"id": 1, "content": "旧伏笔"}]
    assert payload["related_chapters"] == [{"chapter_number": 2, "summary": "前文摘要"}]
    assert payload["active_plot_threads"] == [{"thread_name": "寻找真相"}]
