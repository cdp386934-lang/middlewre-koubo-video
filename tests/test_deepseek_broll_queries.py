from src.services.deepseek_service import DeepSeekService


def test_generate_broll_queries_uses_fallback_when_response_invalid_json():
    service = DeepSeekService.__new__(DeepSeekService)
    service.config = {"broll_query": {"fallback_count": 3}}
    service._chat = lambda *args, **kwargs: "not json"

    queries = service.generate_broll_queries("城市夜景", "讲解城市节奏")
    assert len(queries) == 3
    assert queries[0].startswith("城市夜景")


def test_generate_broll_queries_parses_json_array():
    service = DeepSeekService.__new__(DeepSeekService)
    service.config = {"broll_query": {"fallback_count": 3}}
    service._chat = lambda *args, **kwargs: '["city night skyline", "urban traffic time lapse", "clean street b roll"]'

    queries = service.generate_broll_queries("城市夜景", "讲解城市节奏")
    assert queries == ["city night skyline", "urban traffic time lapse", "clean street b roll"]
