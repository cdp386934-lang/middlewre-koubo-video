from pathlib import Path

from src.models.keyword import Keyword
from src.models.subtitle import SubtitleData, SubtitleSegment
from src.modules.breath_removal import BreathRemovalModule
from src.modules.keyword_extractor import KeywordExtractor


class FakeDeepSeekService:
    def __init__(self, keywords):
        self._keywords = keywords

    def extract_keywords(self, text: str):
        return self._keywords


def test_breath_removal_keeps_short_speech_segments_and_inserts_gap_markers():
    module = BreathRemovalModule(
        {
            "breath_removal": {
                "enabled": True,
                "gap_threshold": 0.5,
                "min_segment_duration": 0.1,
            }
        }
    )

    subtitle_data = SubtitleData(
        segments=[
            SubtitleSegment(id=1, start=0.0, end=0.05, text="嗯"),
            SubtitleSegment(id=2, start=1.0, end=2.0, text="正式内容"),
        ],
        duration=2.0,
    )

    result = module.process(subtitle_data)

    assert [segment.id for segment in result.segments] == [1, 2, 3]
    assert [segment.text for segment in result.segments] == ["嗯", "[BREATH]", "正式内容"]
    assert [segment.removed for segment in result.segments] == [0, 1, 0]


def test_keyword_extractor_applies_auto_jianying_style_annotations(tmp_path: Path):
    extractor = KeywordExtractor.__new__(KeywordExtractor)
    extractor.config = {
        "paths": {"keywords": str(tmp_path)},
        "keyword": {"max_count": 10},
    }
    extractor.deepseek_service = FakeDeepSeekService(
        [
            Keyword(word="完整句子", importance=0.95),
            Keyword(word="关键词", importance=0.85),
            Keyword(word="补充", importance=0.7),
        ]
    )

    subtitle_data = SubtitleData(
        segments=[
            SubtitleSegment(id=1, start=0.0, end=1.0, text="完整句子"),
            SubtitleSegment(id=2, start=1.0, end=2.0, text="这里有关键词和补充"),
            SubtitleSegment(id=3, start=2.0, end=2.5, text="[BREATH]", removed=1),
        ],
        duration=2.5,
    )

    keyword_path = tmp_path / "keywords.json"
    keyword_data = extractor.extract(subtitle_data, output_path=keyword_path)

    assert subtitle_data.segments[0].keyword == "完整句子"
    assert subtitle_data.segments[0].text_grade == 3
    assert subtitle_data.segments[0].video_grade == 2

    assert subtitle_data.segments[1].keyword == "关键词"
    assert subtitle_data.segments[1].keywords == ["关键词", "补充"]
    assert subtitle_data.segments[1].text_grade == 2
    assert subtitle_data.segments[1].video_grade == 1

    assert subtitle_data.segments[2].keyword == ""
    assert subtitle_data.segments[2].text_grade == 1
    assert subtitle_data.segments[2].video_grade == 1

    assert [keyword.word for keyword in keyword_data.keywords] == ["完整句子", "关键词", "补充"]
    assert keyword_data.keywords[0].positions == [1]
    assert keyword_data.keywords[1].positions == [2]
    assert keyword_data.keywords[2].positions == [2]
    assert keyword_path.exists()
