from src.modules.draft_generator import DraftGenerator
from src.models.subtitle import SubtitleData, SubtitleSegment


class TestDraftGeneratorTimeline:
    def setup_method(self):
        self.generator = DraftGenerator.__new__(DraftGenerator)
        self.generator.config = {
            "breath_removal": {
                "merge_tolerance": 0.0,
            },
            "subtitle": {
                "font_size": 24,
                "keyword_color": "#FFD700",
                "keyword_font_size": 28,
            },
        }

    def test_build_timeline_entries_and_captions(self):
        subtitle_data = SubtitleData(
            segments=[
                SubtitleSegment(id=0, start=0.0, end=1.0, text="第一句"),
                SubtitleSegment(id=1, start=1.5, end=2.0, text="[BREATH]", removed=1),
                SubtitleSegment(id=2, start=2.0, end=3.0, text="第二句", keyword="第二", keywords=["第二"], text_grade=2),
            ],
            duration=3.0,
        )

        entries = self.generator._build_timeline_entries(subtitle_data)
        captions = self.generator._prepare_captions(entries)

        assert len(entries) == 2
        assert entries[0]["target_start"] == 0.0
        assert entries[0]["target_end"] == 1.0
        assert entries[1]["target_start"] == 1.0
        assert entries[1]["target_end"] == 2.0

        assert captions == [
            {"start": 0, "end": 1_000_000, "text": "第一句", "font_size": 24},
            {
                "start": 1_000_000,
                "end": 2_000_000,
                "text": "第二句",
                "font_size": 24,
                "keyword": "第二",
                "keyword_color": "#FFD700",
                "keyword_font_size": 28,
            },
        ]

    def test_prepare_video_segments_uses_source_and_target_timerange(self):
        timeline_entries = [
            {
                "segment_id": 0,
                "text": "第一句",
                "source_start": 0.0,
                "source_end": 1.0,
                "target_start": 0.0,
                "target_end": 1.0,
            },
            {
                "segment_id": 1,
                "text": "第二句",
                "source_start": 2.0,
                "source_end": 3.5,
                "target_start": 1.0,
                "target_end": 2.5,
            },
        ]

        video_segments = self.generator._prepare_video_segments(timeline_entries)

        assert video_segments == [
            {"source_start": 0.0, "source_end": 1.0, "target_start": 0.0},
            {"source_start": 2.0, "source_end": 3.5, "target_start": 1.0},
        ]

    def test_prepare_video_segments_respects_video_grade_breaks(self):
        timeline_entries = [
            {
                "segment_id": 1,
                "text": "第一句",
                "keyword": "",
                "keywords": [],
                "text_grade": 1,
                "video_grade": 1,
                "source_start": 0.0,
                "source_end": 1.0,
                "target_start": 0.0,
                "target_end": 1.0,
            },
            {
                "segment_id": 2,
                "text": "重点句",
                "keyword": "重点句",
                "keywords": ["重点句"],
                "text_grade": 3,
                "video_grade": 2,
                "source_start": 1.0,
                "source_end": 2.0,
                "target_start": 1.0,
                "target_end": 2.0,
            },
        ]

        video_segments = self.generator._prepare_video_segments(timeline_entries)

        assert video_segments == [
            {"source_start": 0.0, "source_end": 1.0, "target_start": 0.0},
            {"source_start": 1.0, "source_end": 2.0, "target_start": 1.0},
        ]
