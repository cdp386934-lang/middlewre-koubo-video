#!/usr/bin/env python3
"""
按 GEN_VIDEO_STATUS 文档测试云渲染状态查询：
- 支持传 draft_url 或 draft_id
- 可选先触发 gen_video 提交任务
- 轮询并写日志到 output/test_gen_video_status.log
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlparse, urlunparse

import requests
import yaml


def load_config(config_path: Path) -> Dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def resolve_env_value(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("${") and text.endswith("}"):
        env_var = text[2:-1]
        text = str(os.getenv(env_var) or "").strip()
    return text


def normalize_get_draft_base(raw_base: str) -> str:
    raw_base = (raw_base or "").strip()
    if not raw_base:
        return ""

    parsed = urlparse(raw_base)
    if parsed.path in {"", "/"}:
        parsed = parsed._replace(path="/openapi/capcut-mate/v1/get_draft")
    parsed = parsed._replace(query="", fragment="")
    return urlunparse(parsed).rstrip("?")


def resolve_draft_url(draft_url: Optional[str], draft_id: Optional[str], get_draft_base: str) -> str:
    if draft_url and draft_url.strip():
        return draft_url.strip()

    if draft_id and draft_id.strip():
        query = urlencode({"draft_id": draft_id.strip()})
        return f"{get_draft_base}?{query}"

    raise ValueError("必须提供 --draft-url 或 --draft-id 其中一个参数")


def append_log(log_path: Path, payload: Dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def post_json(url: str, body: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    resp = requests.post(url, json=body, timeout=timeout)
    resp.raise_for_status()
    return resp.json()

def ensure_success(payload: Dict[str, Any], context: str) -> Dict[str, Any]:
    """
    兼容 capcut-mate 的两种响应风格：
    - 统一封装：{code,message,...}
    - 未封装：直接返回业务字段（文档示例）
    """
    if isinstance(payload, dict) and "code" in payload:
        code = payload.get("code")
        try:
            code = int(code)
        except (TypeError, ValueError):
            pass
        if code != 0:
            message = payload.get("message") or payload.get("detail") or ""
            raise RuntimeError(f"{context} 失败: code={code} message={message}".strip())
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="测试 capcut-mate gen_video_status 接口并保存日志")
    parser.add_argument("--draft-url", dest="draft_url", help="完整草稿 URL（优先使用）")
    parser.add_argument("--draft-id", dest="draft_id", help="草稿 ID（会自动拼接 get_draft URL）")
    parser.add_argument("--submit", action="store_true", help="先调用 gen_video 提交任务，再轮询状态")
    parser.add_argument("--api-key", dest="api_key", default="", help="提交任务时可选的 apiKey")
    parser.add_argument("--interval", type=float, default=5.0, help="轮询间隔秒数，默认 5")
    parser.add_argument("--timeout-seconds", type=int, default=600, help="总超时时间，默认 600 秒")
    parser.add_argument(
        "--log-file",
        default="output/test_gen_video_status.log",
        help="日志文件路径，默认 output/test_gen_video_status.log",
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="配置文件路径，默认 config/config.yaml",
    )
    parser.add_argument(
        "--get-draft-base",
        default="",
        help="拼接 draft_id 时使用的 get_draft base URL；默认优先使用 capcut.cloud_render.draft_url_base，其次 capcut.api_url",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    config_path = (project_root / args.config).resolve()
    config = load_config(config_path)
    capcut_cfg = (config.get("capcut") or {})
    cloud_cfg = (capcut_cfg.get("cloud_render") or {})
    capcut_api_base = resolve_env_value(capcut_cfg.get("api_url") or "http://localhost:30000").rstrip("/")
    cloud_api_base = resolve_env_value(cloud_cfg.get("api_url") or "").rstrip("/")
    api_base = (cloud_api_base or capcut_api_base).rstrip("/")
    request_timeout = int(capcut_cfg.get("timeout", 30))

    cloud_draft_url_base = normalize_get_draft_base(resolve_env_value(cloud_cfg.get("draft_url_base") or ""))
    default_get_draft_base = cloud_draft_url_base or f"{capcut_api_base}/openapi/capcut-mate/v1/get_draft"
    get_draft_base = args.get_draft_base.strip() or default_get_draft_base
    draft_url = resolve_draft_url(
        draft_url=args.draft_url,
        draft_id=args.draft_id,
        get_draft_base=get_draft_base,
    )

    log_path = (project_root / args.log_file).resolve()
    gen_video_endpoint = f"{api_base}/openapi/capcut-mate/v1/gen_video"
    status_endpoint = f"{api_base}/openapi/capcut-mate/v1/gen_video_status"

    print(f"api_base: {api_base}")
    print(f"draft_url: {draft_url}")
    print(f"log_file: {log_path}")

    if args.submit:
        submit_payload: Dict[str, Any] = {"draft_url": draft_url}
        if args.api_key.strip():
            submit_payload["apiKey"] = args.api_key.strip()

        submit_result = ensure_success(
            post_json(gen_video_endpoint, submit_payload, timeout=request_timeout),
            context="gen_video 提交",
        )
        append_log(
            log_path,
            {
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "step": "gen_video_submit",
                "request": submit_payload,
                "response": submit_result,
            },
        )
        print("gen_video 提交响应:")
        print(json.dumps(submit_result, ensure_ascii=False, indent=2))

    start = time.time()
    max_wait = max(args.timeout_seconds, 1)
    interval = max(args.interval, 0.5)

    while True:
        elapsed = time.time() - start
        if elapsed > max_wait:
            timeout_payload = {
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "step": "poll_timeout",
                "elapsed_seconds": round(elapsed, 2),
                "timeout_seconds": max_wait,
            }
            append_log(log_path, timeout_payload)
            print(json.dumps(timeout_payload, ensure_ascii=False, indent=2))
            return 2

        body = {"draft_url": draft_url}
        status_result = ensure_success(
            post_json(status_endpoint, body, timeout=request_timeout),
            context="gen_video_status 查询",
        )

        status = str(status_result.get("status", "")).lower()
        progress = status_result.get("progress")

        row = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "step": "gen_video_status",
            "elapsed_seconds": round(elapsed, 2),
            "request": body,
            "response": status_result,
        }
        append_log(log_path, row)

        print(f"[{row['ts']}] status={status or 'unknown'} progress={progress}")

        if status in {"completed", "failed"}:
            print("最终状态:")
            print(json.dumps(status_result, ensure_ascii=False, indent=2))
            return 0 if status == "completed" else 1

        time.sleep(interval)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as exc:
        print(f"HTTP 错误: {exc}")
        if exc.response is not None:
            print(exc.response.text)
        raise SystemExit(3)
    except Exception as exc:  # noqa: BLE001
        print(f"执行失败: {exc}")
        raise SystemExit(4)
