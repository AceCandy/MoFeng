from app.api.routers.novels import StreamingJSONFieldExtractor


def test_streaming_json_field_extractor_emits_ai_message_deltas():
    extractor = StreamingJSONFieldExtractor("ai_message")

    chunks = [
        '{"ai_message":"你好',
        '，创作者',
        '\\n我们开始吧","ui_control":{"type":"text_input"}}',
    ]

    emitted = [delta for chunk in chunks if (delta := extractor.feed(chunk))]

    assert emitted == ["你好", "，创作者", "\n我们开始吧"]
