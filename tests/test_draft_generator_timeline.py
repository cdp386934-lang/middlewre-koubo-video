from pathlib import Path
from src.models.keyword import KeywordData
from src.modules.draft_generator import DraftGenerator
from src.models.subtitle import SubtitleData, SubtitleSegment


class FakeCapCutService:
    def __init__(self):
        self.calls = []

    def create_draft(self, width, height):
        self.calls.append(("create_draft", width, height))
        return "draft-001"

    def add_videos(self, video_paths, start_time=0.0):
        self.calls.append(("add_videos", list(video_paths), start_time))
        return {"code": 0}

    def add_video_segments(self, video_path, segments):
        self.calls.append(("add_video_segments", video_path, list(segments)))
        return {"code": 0}

    def add_background_image(self, image_path, width, height, duration, alpha=1.0):
        self.calls.append(("add_background_image", str(image_path), width, height, duration, alpha))
        return {"code": 0}

    def add_captions(self, captions, options=None):
        self.calls.append(("add_captions", list(captions), options))
        return {"code": 0}

    def save_draft(self):
        self.calls.append(("save_draft",))
        return "draft-path"

    def add_video_material(self, video_source, start_time, duration, track_index=2):
        self.calls.append(("add_video_material", video_source, start_time, duration, track_index))
        return {"code": 0}

    def add_image_material(self, image_source, start_time, duration, track_index=2):
        self.calls.append(("add_image_material", image_source, start_time, duration, track_index))
        return {"code": 0}


class TestDraftGeneratorTimeline:
    def setup_method(self):
        self.generator = DraftGenerator.__new__(DraftGenerator)
        self.generator.config = {
            "paths": {
                "drafts": "/tmp",
                "input": "/tmp/input",
            },
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
                SubtitleSegment(id=1, start=1.0, end=2.0, text="[BREATH]", removed=1),
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
                "text": "\"第二\"句",
                "font_size": 24,
                "keyword": "\"第二\"",
                "keyword_color": "#FFD700",
                "keyword_font_size": 28,
            },
        ]

    def test_build_timeline_entries_preserves_unremoved_gaps(self):
        subtitle_data = SubtitleData(
            segments=[
                SubtitleSegment(id=1, start=0.0, end=1.0, text="第一句"),
                SubtitleSegment(id=2, start=1.4, end=2.0, text="第二句"),
            ],
            duration=2.0,
        )

        entries = self.generator._build_timeline_entries(subtitle_data)

        assert len(entries) == 2
        assert entries[0]["target_start"] == 0.0
        assert entries[0]["target_end"] == 1.0
        assert entries[1]["target_start"] == 1.4
        assert entries[1]["target_end"] == 2.0

    def test_prepare_video_segments_merges_entries_when_gap_is_preserved(self):
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
                "text": "第二句",
                "keyword": "",
                "keywords": [],
                "text_grade": 1,
                "video_grade": 1,
                "source_start": 1.4,
                "source_end": 2.0,
                "target_start": 1.4,
                "target_end": 2.0,
            },
        ]

        video_segments = self.generator._prepare_video_segments(timeline_entries)

        assert video_segments == [
            {"source_start": 0.0, "source_end": 2.0, "target_start": 0.0},
        ]

    def test_has_removed_segments_only_when_explicitly_marked(self):
        without_removed = SubtitleData(
            segments=[
                SubtitleSegment(id=1, start=0.0, end=1.0, text="第一句"),
            ],
            duration=1.0,
        )
        with_removed = SubtitleData(
            segments=[
                SubtitleSegment(id=1, start=0.0, end=1.0, text="第一句"),
                SubtitleSegment(id=2, start=1.0, end=1.5, text="[BREATH]", removed=1),
            ],
            duration=1.5,
        )

        assert self.generator._has_removed_segments(without_removed) is False
        assert self.generator._has_removed_segments(with_removed) is True

    def test_generate_uses_full_video_when_no_removed_segments(self, tmp_path):
        generator = DraftGenerator.__new__(DraftGenerator)
        generator.config = {
            "paths": {
                "drafts": str(tmp_path),
                "input": str(tmp_path / "input"),
            },
            "breath_removal": {
                "merge_tolerance": 0.0,
            },
            "subtitle": {
                "font_size": 24,
                "keyword_color": "#FFD700",
                "keyword_font_size": 28,
            },
            "overlay_text": {},
        }
        generator.capcut_service = FakeCapCutService()
        generator._ensure_capcut_compatible_video = lambda video_path: Path(video_path)
        generator._build_overlay_texts = lambda duration, generated_title, video_layout=None: []
        generator._add_overlay_texts = lambda overlay_texts: None

        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"")

        subtitle_data = SubtitleData(
            segments=[
                SubtitleSegment(id=1, start=0.0, end=1.0, text="第一句"),
                SubtitleSegment(id=2, start=1.4, end=2.0, text="第二句"),
            ],
            duration=2.0,
        )

        generator.generate(
            video_path=video_path,
            subtitle_data=subtitle_data,
            keyword_data=KeywordData(keywords=[]),
            video_info={"width": 1080, "height": 1920, "duration": 2.0, "resolution": "1080x1920", "fps": 30},
        )

        call_names = [call[0] for call in generator.capcut_service.calls]
        assert "add_videos" in call_names
        assert "add_video_segments" not in call_names

    def test_generate_adds_vertical_background_before_main_video(self, tmp_path):
        generator = DraftGenerator.__new__(DraftGenerator)
        generator.config = {
            "paths": {
                "drafts": str(tmp_path),
                "input": str(tmp_path / "input"),
                "temp": str(tmp_path / "temp"),
            },
            "breath_removal": {
                "merge_tolerance": 0.0,
            },
            "subtitle": {
                "font_size": 24,
                "font_color": "#333333",
                "keyword_color": "#C9A227",
                "keyword_font_size": 28,
                "transform_y": 780,
                "has_shadow": False,
            },
            "overlay_text": {},
            "draft_layout": {
                "enabled": True,
                "width": 1080,
                "height": 1920,
                "background_color": "#F2F1EC",
                "main_video": {
                    "max_width": 960,
                    "max_height": 980,
                    "transform_x": 0,
                    "transform_y": 0,
                },
            },
        }
        generator.capcut_service = FakeCapCutService()
        generator._ensure_capcut_compatible_video = lambda video_path: Path(video_path)
        generator._build_overlay_texts = lambda duration, generated_title, video_layout=None: []
        generator._add_overlay_texts = lambda overlay_texts: None
        generator._ensure_background_image = lambda draft_name, draft_layout, video_layout=None: tmp_path / "cover-bg.png"
        generator._apply_main_video_layout_to_local_draft = lambda video_info, draft_layout: None

        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"")

        subtitle_data = SubtitleData(
            segments=[
                SubtitleSegment(id=1, start=0.0, end=1.0, text="第一句"),
            ],
            duration=1.0,
        )

        generator.generate(
            video_path=video_path,
            subtitle_data=subtitle_data,
            keyword_data=KeywordData(keywords=[]),
            video_info={"width": 960, "height": 544, "duration": 1.0, "resolution": "960x544", "fps": 30},
        )

        assert generator.capcut_service.calls[0] == ("create_draft", 1080, 1920)
        assert generator.capcut_service.calls[1] == ("add_background_image", str(tmp_path / "cover-bg.png"), 1080, 1920, 1.0, 1.0)
        assert generator.capcut_service.calls[2] == ("add_videos", [str(video_path)], 0.0)

    def test_apply_video_layout_to_draft_content_updates_main_track_only(self):
        draft_content = {
            "tracks": [
                {
                    "type": "video",
                    "segments": [
                        {
                            "clip": {
                                "scale": {"x": 1.0, "y": 1.0},
                                "transform": {"x": 0.0, "y": 0.0},
                            },
                            "uniform_scale": {"on": True, "value": 1.0},
                        }
                    ],
                },
                {
                    "type": "video",
                    "segments": [
                        {
                            "clip": {
                                "scale": {"x": 1.0, "y": 1.0},
                                "transform": {"x": 0.0, "y": 0.0},
                            },
                            "uniform_scale": {"on": True, "value": 1.0},
                        },
                        {
                            "clip": {
                                "scale": {"x": 1.0, "y": 1.0},
                                "transform": {"x": 0.0, "y": 0.0},
                            },
                            "uniform_scale": {"on": True, "value": 1.0},
                        },
                    ],
                },
            ]
        }

        changed = DraftGenerator._apply_video_layout_to_draft_content(
            draft_content=draft_content,
            scale=0.72,
            transform_x=0.0,
            transform_y=0.0,
        )

        assert changed is True
        assert draft_content["tracks"][0]["segments"][0]["clip"]["scale"] == {"x": 1.0, "y": 1.0}
        for segment in draft_content["tracks"][1]["segments"]:
            assert segment["clip"]["scale"] == {"x": 0.72, "y": 0.72}
            assert segment["uniform_scale"] == {"on": True, "value": 0.72}

    def test_build_overlay_texts_spans_full_duration_and_tracks_video_position(self):
        self.generator.config["overlay_text"] = {
            "title": {
                "enabled": True,
                "full_duration": True,
                "font_size": 40,
                "anchor_to_video": True,
                "margin_to_video": 96,
                "text_color": "#333333",
            },
            "author": {
                "enabled": True,
                "full_duration": True,
                "anchor_to_video": True,
                "margin_to_video": 60,
                "line_gap": 28,
                "name": "作者A",
                "identity": "作者简介",
                "name_font_size": 24,
                "identity_font_size": 20,
            },
        }
        video_layout = {"top": -272.0, "bottom": 272.0}

        overlays = self.generator._build_overlay_texts(
            duration=12.5,
            generated_title="标题测试",
            video_layout=video_layout,
        )

        title_overlay = next(item for item in overlays if item["name"] == "title")
        author_name_overlay = next(item for item in overlays if item["name"] == "author_name")
        author_identity_overlay = next(item for item in overlays if item["name"] == "author_identity")

        assert title_overlay["captions"][0]["end"] == 12_500_000
        assert author_name_overlay["captions"][0]["end"] == 12_500_000
        assert author_identity_overlay["captions"][0]["end"] == 12_500_000
        assert title_overlay["options"]["transform_y"] < video_layout["top"]
        assert author_name_overlay["options"]["transform_y"] > video_layout["bottom"]
        assert author_identity_overlay["options"]["transform_y"] > author_name_overlay["options"]["transform_y"]

    def test_build_subtitle_options_places_caption_below_video(self):
        self.generator.config["subtitle"] = {
            "font_size": 24,
            "font_color": "#333333",
            "keyword_color": "#C9A227",
            "keyword_font_size": 28,
            "anchor_to_video": True,
            "margin_to_video": 72,
            "has_shadow": False,
        }

        options = self.generator._build_subtitle_options(
            draft_layout={"enabled": True},
            video_layout={"bottom": 272.0},
        )

        assert options["transform_y"] == 356.0
        assert options["has_shadow"] is False

    def test_needs_capcut_video_normalization_when_audio_sample_rate_uncommon(self):
        probe = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p"},
                {"codec_type": "audio", "codec_name": "aac", "sample_rate": "32000", "channels": 2},
            ]
        }

        assert DraftGenerator._needs_capcut_video_normalization(probe) is True

    def test_get_target_draft_duration_uses_full_video_minus_removed_segments(self):
        subtitle_data = SubtitleData(
            segments=[
                SubtitleSegment(id=1, start=0.0, end=2.0, text="前半段"),
                SubtitleSegment(id=2, start=2.0, end=3.0, text="[BREATH]", removed=1),
            ],
            duration=3.0,
        )

        duration = DraftGenerator._get_target_draft_duration(
            subtitle_data,
            {"duration": 10.0},
        )

        assert duration == 9.0

    def test_generate_uses_capcut_ready_video_path(self, tmp_path):
        generator = DraftGenerator.__new__(DraftGenerator)
        generator.config = {
            "paths": {
                "drafts": str(tmp_path),
                "input": str(tmp_path / "input"),
            },
            "breath_removal": {
                "merge_tolerance": 0.0,
            },
            "subtitle": {
                "font_size": 24,
                "font_color": "#333333",
                "keyword_color": "#C9A227",
                "keyword_font_size": 28,
            },
            "overlay_text": {},
        }
        generator.capcut_service = FakeCapCutService()
        ready_video_path = tmp_path / "video_capcut_ready.mp4"
        ready_video_path.write_bytes(b"")
        generator._ensure_capcut_compatible_video = lambda video_path: ready_video_path
        generator._ensure_background_track = lambda draft_name, duration, draft_layout: None
        generator._build_overlay_texts = lambda duration, generated_title, video_layout=None: []
        generator._add_overlay_texts = lambda overlay_texts: None
        generator._apply_main_video_layout_to_local_draft = lambda video_info, draft_layout: None

        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"")
        subtitle_data = SubtitleData(
            segments=[SubtitleSegment(id=1, start=0.0, end=1.0, text="第一句")],
            duration=1.0,
        )

        generator.generate(
            video_path=video_path,
            subtitle_data=subtitle_data,
            keyword_data=KeywordData(keywords=[]),
            video_info={"width": 960, "height": 544, "duration": 1.0, "resolution": "960x544", "fps": 30},
        )

        assert ("add_videos", [str(ready_video_path)], 0.0) in generator.capcut_service.calls

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


    def test_add_materials_prefers_local_path_and_sets_processed_path(self, tmp_path):
        from src.models.material import Material, MaterialData

        generator = DraftGenerator.__new__(DraftGenerator)
        generator.config = {"paths": {"temp": str(tmp_path / "temp")}}
        generator.capcut_service = FakeCapCutService()
        generator._ensure_capcut_compatible_broll_video = lambda p: Path(p)

        local_video = tmp_path / "mat.mp4"
        local_video.write_bytes(b"video")
        material = Material(
            id=1,
            type="video",
            keyword="测试",
            source_query="test query",
            url="https://pexels.com/video/1",
            download_url="https://cdn.pexels.com/video.mp4",
            local_path=str(local_video),
            width=1920,
            height=1080,
            duration=5.0,
            photographer="a",
            photographer_url="https://pexels.com/@a",
            segment_id=1,
        )
        material_data = MaterialData(materials=[material])
        timeline_entries = [{
            "segment_id": 1,
            "target_start": 2.0,
            "target_end": 6.0,
        }]

        generator._add_materials_to_draft("draft-001", material_data, timeline_entries)

        assert ("add_video_material", str(local_video), 2.0, 4.0, 2) in generator.capcut_service.calls
        assert material.processed_path == str(local_video)
