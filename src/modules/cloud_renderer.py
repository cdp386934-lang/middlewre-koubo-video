import os
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

from loguru import logger

from ..services.capcut_service import CapCutService


class CloudRenderer:
    """云渲染模块：封装任务提交和轮询。"""

    GET_DRAFT_PATH = "/openapi/capcut-mate/v1/get_draft"

    def __init__(self, config: Dict[str, Any], capcut_service: CapCutService):
        self.config = config
        self.capcut_service = capcut_service
        self.render_config = (config.get("capcut", {}) or {}).get("cloud_render", {}) or {}

    def is_enabled(self) -> bool:
        return bool(self.render_config.get("enabled", False))

    def submit_and_poll(self, draft_url: str) -> Dict[str, Any]:
        """
        提交渲染任务并轮询到完成/失败/超时。

        Returns:
            Dict[str, Any]: 最终状态信息
        """
        poll_interval = float(self.render_config.get("poll_interval_seconds", 5))
        timeout_seconds = float(self.render_config.get("timeout_seconds", 1800))
        submit_task = bool(self.render_config.get("submit", True))
        api_key = self._resolve_api_key() if submit_task else None
        effective_draft_url = self._rewrite_draft_url_if_needed(draft_url)

        if submit_task:
            self.capcut_service.gen_video(draft_url=effective_draft_url, api_key=api_key)
            logger.info(
                f"云渲染任务已提交，开始轮询状态: poll={poll_interval}s timeout={timeout_seconds}s"
            )
        else:
            logger.info(
                f"云渲染提交已禁用，仅轮询状态: poll={poll_interval}s timeout={timeout_seconds}s"
            )

        start_time = time.time()
        last_status: Dict[str, Any] = {}

        while True:
            try:
                status_info = self.capcut_service.gen_video_status(
                    draft_url=effective_draft_url,
                    tolerate_not_found=not submit_task,
                )
            except TypeError:
                # 兼容测试桩或旧接口签名（不支持 tolerate_not_found 参数）
                status_info = self.capcut_service.gen_video_status(draft_url=effective_draft_url)
            if (
                (not submit_task)
                and isinstance(status_info, dict)
                and int(status_info.get("code", 0) or 0) == 2031
            ):
                logger.warning("仅轮询模式下未找到渲染任务，跳过云渲染轮询")
                return {
                    "status": "not_found",
                    "progress": 0,
                    "video_url": "",
                    "error_message": "未找到对应渲染任务（仅轮询模式不会自动提交）",
                    "draft_url": effective_draft_url,
                }
            last_status = status_info
            status = str(status_info.get("status", "")).lower()
            progress = status_info.get("progress", 0)
            logger.info(f"云渲染状态: status={status}, progress={progress}%")

            if status == "completed":
                return status_info
            if status == "failed":
                return status_info

            if time.time() - start_time > timeout_seconds:
                timeout_result = dict(last_status)
                timeout_result["status"] = "timeout"
                timeout_result["error_message"] = (
                    timeout_result.get("error_message")
                    or f"云渲染轮询超时（>{int(timeout_seconds)}秒）"
                )
                return timeout_result

            time.sleep(max(poll_interval, 0.5))

    def _resolve_api_key(self) -> Optional[str]:
        """读取并校验云渲染 API Key。"""
        api_key = self.render_config.get("api_key")
        if api_key is None:
            raise ValueError("云渲染已启用，但未配置 capcut.cloud_render.api_key")

        api_key = str(api_key).strip()
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = str(os.getenv(env_var) or "").strip()

        if not api_key:
            raise ValueError("云渲染已启用，但 capcut.cloud_render.api_key 为空")

        return api_key

    def _rewrite_draft_url_if_needed(self, draft_url: str) -> str:
        """将 draft_url 重写为云渲染可访问的远程路由（可选）。"""
        base = str(self.render_config.get("draft_url_base") or "").strip()
        if base.startswith("${") and base.endswith("}"):
            env_var = base[2:-1]
            base = str(os.getenv(env_var) or "").strip()

        if not base:
            return draft_url

        draft_id = self._extract_draft_id(draft_url)
        if not draft_id:
            return draft_url

        parsed = urlparse(base)
        # 允许只填域名（无 path）时自动补齐 get_draft 路径
        normalized_path = parsed.path or ""
        if normalized_path in {"", "/"}:
            parsed = parsed._replace(path=self.GET_DRAFT_PATH)
        parsed = parsed._replace(query="", fragment="")
        cleaned_base = urlunparse(parsed).rstrip("?")
        sep = "&" if "?" in cleaned_base else "?"
        return f"{cleaned_base}{sep}{urlencode({'draft_id': draft_id})}"

    @staticmethod
    def _extract_draft_id(draft_url: str) -> str:
        parsed = urlparse(str(draft_url or ""))
        params = parse_qs(parsed.query)
        return str(params.get("draft_id", [""])[0] or "")
