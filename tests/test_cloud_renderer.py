import json
from typing import Any, Dict, List, Optional

import pytest
import requests

import src.modules.cloud_renderer as cloud_renderer_module
from src.modules.cloud_renderer import CloudRenderer
from src.services.capcut_service import CapCutService


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(payload, ensure_ascii=False)

    def raise_for_status(self) -> None:
        if 200 <= int(self.status_code) < 300:
            return
        raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self) -> Any:
        return self._payload


class FakeCapCutService:
    def __init__(self, statuses: List[Dict[str, Any]]):
        self._statuses = statuses
        self.gen_video_calls: List[Dict[str, Optional[str]]] = []
        self.status_calls = 0

    def gen_video(self, draft_url: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        self.gen_video_calls.append({"draft_url": draft_url, "api_key": api_key})
        return {"message": "ok"}

    def gen_video_status(self, draft_url: str) -> Dict[str, Any]:
        idx = min(self.status_calls, max(len(self._statuses) - 1, 0))
        self.status_calls += 1
        return dict(self._statuses[idx])


def test_capcut_service_request_accepts_doc_style_success(monkeypatch, tmp_path):
    service = CapCutService({"capcut": {"api_url": "http://example", "draft_root": str(tmp_path)}})

    def fake_post(url, json=None, timeout=30):
        return FakeResponse({"status": "processing", "progress": 65, "video_url": ""})

    monkeypatch.setattr(requests, "post", fake_post)
    result = service._request("/openapi/capcut-mate/v1/gen_video_status", data={"draft_url": "x"})
    assert result["status"] == "processing"
    assert result["progress"] == 65


def test_capcut_service_request_handles_wrapped_success(monkeypatch, tmp_path):
    service = CapCutService({"capcut": {"api_url": "http://example", "draft_root": str(tmp_path)}})

    def fake_post(url, json=None, timeout=30):
        return FakeResponse({"code": "0", "message": "ok", "status": "pending", "progress": 0})

    monkeypatch.setattr(requests, "post", fake_post)
    result = service._request("/openapi/capcut-mate/v1/gen_video_status", data={"draft_url": "x"})
    assert result["status"] == "pending"
    assert result["progress"] == 0


def test_capcut_service_request_raises_on_wrapped_error(monkeypatch, tmp_path):
    service = CapCutService({"capcut": {"api_url": "http://example", "draft_root": str(tmp_path)}})

    def fake_post(url, json=None, timeout=30):
        return FakeResponse({"code": 400, "message": "Invalid draft URL"})

    monkeypatch.setattr(requests, "post", fake_post)
    with pytest.raises(ValueError, match="Invalid draft URL"):
        service._request("/openapi/capcut-mate/v1/gen_video_status", data={"draft_url": "x"})


def test_capcut_service_request_raises_on_detail_error(monkeypatch, tmp_path):
    service = CapCutService({"capcut": {"api_url": "http://example", "draft_root": str(tmp_path)}})

    def fake_post(url, json=None, timeout=30):
        return FakeResponse({"detail": "Video generation task not found"})

    monkeypatch.setattr(requests, "post", fake_post)
    with pytest.raises(ValueError, match="Video generation task not found"):
        service._request("/openapi/capcut-mate/v1/gen_video_status", data={"draft_url": "x"})


def test_cloud_renderer_submit_and_poll_returns_completed(monkeypatch):
    renderer = CloudRenderer(
        {
            "capcut": {
                "cloud_render": {
                    "enabled": True,
                    "api_key": "k",
                    "poll_interval_seconds": 0.01,
                    "timeout_seconds": 10,
                }
            }
        },
        FakeCapCutService(
            [
                {"status": "pending", "progress": 0},
                {"status": "processing", "progress": 50},
                {"status": "completed", "progress": 100, "video_url": "https://example/video.mp4"},
            ]
        ),
    )

    monkeypatch.setattr(cloud_renderer_module.time, "sleep", lambda _: None)

    result = renderer.submit_and_poll("draft_url")
    assert result["status"] == "completed"
    assert result["progress"] == 100


def test_cloud_renderer_submit_and_poll_times_out(monkeypatch):
    service = FakeCapCutService([{"status": "processing", "progress": 1}])
    renderer = CloudRenderer(
        {
            "capcut": {
                "cloud_render": {
                    "enabled": True,
                    "api_key": "k",
                    "poll_interval_seconds": 0.01,
                    "timeout_seconds": 2,
                }
            }
        },
        service,
    )

    monkeypatch.setattr(cloud_renderer_module.time, "sleep", lambda _: None)

    now = {"t": 0.0}

    def fake_time() -> float:
        now["t"] += 1.0
        return now["t"]

    monkeypatch.setattr(cloud_renderer_module.time, "time", fake_time)

    result = renderer.submit_and_poll("draft_url")
    assert result["status"] == "timeout"
    assert "超时" in (result.get("error_message") or "")


def test_cloud_renderer_resolves_api_key_from_env(monkeypatch):
    monkeypatch.setenv("CAPCUT_MATE_API_KEY", "k")
    service = FakeCapCutService([{"status": "completed", "progress": 100}])
    renderer = CloudRenderer(
        {
            "capcut": {
                "cloud_render": {
                    "enabled": True,
                    "api_key": "${CAPCUT_MATE_API_KEY}",
                    "poll_interval_seconds": 0.01,
                    "timeout_seconds": 10,
                }
            }
        },
        service,
    )

    monkeypatch.setattr(cloud_renderer_module.time, "sleep", lambda _: None)

    renderer.submit_and_poll("draft_url")
    assert service.gen_video_calls[0]["api_key"] == "k"
