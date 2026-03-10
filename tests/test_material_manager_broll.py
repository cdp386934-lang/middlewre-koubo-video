from src.modules.material_manager import MaterialManager


def test_filter_videos_respects_duration_and_sorts_candidates():
    manager = MaterialManager.__new__(MaterialManager)
    manager.min_duration = 3
    manager.max_duration = 8
    manager.orientation = "landscape"
    manager.shot_preferences = ["slow motion", "close up"]

    videos = [
        {"id": 1, "duration": 2.5, "width": 1920, "height": 1080, "url": "https://pexels.com/video/a"},
        {"id": 2, "duration": 5.0, "width": 1920, "height": 1080, "url": "https://pexels.com/video/slow-motion-detail"},
        {"id": 3, "duration": 7.0, "width": 1080, "height": 1920, "url": "https://pexels.com/video/close-up-face"},
    ]

    filtered = manager._filter_videos(videos)
    assert [video["id"] for video in filtered] == [2, 3]
