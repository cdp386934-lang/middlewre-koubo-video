import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import parse_qs, urlparse

import requests
from loguru import logger


class CapCutService:
    """CapCut-mate API 客户端"""

    def __init__(self, config: Dict[str, Any], file_server=None):
        self.config = config["capcut"]
        self.api_url = self.config["api_url"]
        self.timeout = self.config.get("timeout", 30)
        self.draft_root = Path(self.config["draft_root"]).expanduser()
        self.draft_url = None  # 保存当前草稿 URL
        self.draft_id = None   # 保存当前草稿 ID
        self.local_draft_dir: Optional[Path] = None
        self.file_server = file_server  # 本地文件服务器
        logger.info(f"CapCut-mate API 客户端初始化完成: {self.api_url}")

    def _request(self, endpoint: str, method: str = "POST", data: Dict = None) -> Dict:
        """发送 API 请求"""
        url = f"{self.api_url}{endpoint}"
        try:
            if method == "POST":
                response = requests.post(url, json=data, timeout=self.timeout)
            else:
                response = requests.get(url, params=data, timeout=self.timeout)

            response.raise_for_status()
            result = response.json()

            # 检查响应状态码
            if result.get("code") != 0:
                error_msg = result.get("message", "未知错误")
                logger.error(f"API 返回错误 [{endpoint}]: {error_msg}")
                raise ValueError(f"API 错误: {error_msg}")

            logger.debug(f"API 响应 [{endpoint}]: {result}")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"API 请求失败 [{endpoint}]: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"响应内容: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"API 请求异常 [{endpoint}]: {e}")
            raise

    def _extract_draft_id(self, draft_url: str) -> str:
        """从 draft_url 中提取 draft_id"""
        parsed = urlparse(draft_url)
        params = parse_qs(parsed.query)
        draft_id = params.get('draft_id', [None])[0]
        if not draft_id:
            raise ValueError(f"无法从 URL 中提取 draft_id: {draft_url}")
        return draft_id

    def _is_draft_in_local_root(self, draft_id: str) -> bool:
        """检查草稿是否已落地到本机剪映草稿目录"""
        if not draft_id:
            return False
        return (self.draft_root / draft_id).exists()

    def _fetch_draft_files(self) -> List[str]:
        """从 get_draft 接口拿到当前草稿的全部文件 URL。"""
        if not self.draft_url:
            raise ValueError("请先调用 create_draft 创建草稿")

        response = requests.get(self.draft_url, timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        if result.get("code") != 0:
            raise ValueError(f"获取草稿详情失败: {result}")

        files = result.get("files", [])
        if not files:
            raise ValueError(f"草稿文件列表为空: draft_id={self.draft_id}")
        return files

    def _download_file(self, file_url: str, destination: Path) -> None:
        """下载单个草稿文件到目标位置。"""
        destination.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(file_url, timeout=max(self.timeout, 120), stream=True) as response:
            response.raise_for_status()
            with open(destination, "wb") as file_obj:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file_obj.write(chunk)

    def _sync_draft_to_local_root(self) -> Path:
        """将 capcut-mate 输出的草稿同步到本机剪映目录。"""
        if not self.draft_id:
            raise ValueError("当前没有可同步的草稿 ID")

        draft_files = self._fetch_draft_files()
        local_draft_dir = self.draft_root / self.draft_id
        self.draft_root.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix=f"{self.draft_id}_") as temp_dir:
            temp_root = Path(temp_dir) / self.draft_id
            temp_root.mkdir(parents=True, exist_ok=True)

            marker = f"/output/draft/{self.draft_id}/"
            for file_url in draft_files:
                parsed = urlparse(file_url)
                path_str = parsed.path
                if marker not in path_str:
                    logger.debug(f"跳过无法识别相对路径的草稿文件: {file_url}")
                    continue

                relative_path = path_str.split(marker, 1)[1]
                destination = temp_root / relative_path
                self._download_file(file_url, destination)

            if local_draft_dir.exists():
                shutil.rmtree(local_draft_dir)

            shutil.copytree(temp_root, local_draft_dir)

        try:
            draft_meta = local_draft_dir / "draft_meta_info.json"
            if draft_meta.exists():
                os.utime(draft_meta, None)
            os.utime(local_draft_dir, None)
            os.utime(self.draft_root, None)
        except Exception as exc:
            logger.debug(f"刷新草稿目录时间失败: {exc}")

        return local_draft_dir

    def create_draft(self, width: int = 1920, height: int = 1080) -> str:
        """
        创建新草稿

        Args:
            width: 视频宽度
            height: 视频高度

        Returns:
            str: 草稿 ID
        """
        logger.info(f"创建草稿: {width}x{height}")
        result = self._request("/openapi/capcut-mate/v1/create_draft", data={
            "width": width,
            "height": height
        })

        self.draft_url = result.get("draft_url")
        if not self.draft_url:
            raise ValueError(f"API 返回的数据中没有 draft_url: {result}")

        self.draft_id = self._extract_draft_id(self.draft_url)
        self.local_draft_dir = None
        logger.info(f"草稿创建成功: {self.draft_id}")
        return self.draft_id

    @staticmethod
    def _resolve_video_duration_us(probe: Dict[str, Any]) -> int:
        """优先使用视频流时长，避免 format.duration 略大导致 add_videos 越界。"""
        streams = probe.get("streams", [])
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)

        duration_us = 0
        if video_stream and video_stream.get("duration") not in (None, ""):
            duration_us = max(int(float(video_stream["duration"]) * 1_000_000), 0)
        else:
            format_duration = probe.get("format", {}).get("duration")
            if format_duration not in (None, ""):
                duration_us = max(int(float(format_duration) * 1_000_000), 0)

        # 减去50ms安全缓冲，避免浮点精度问题导致超出实际视频时长
        if duration_us > 50_000:
            duration_us -= 50_000

        return duration_us

    def add_videos(self, video_paths: List[Union[str, Path]], start_time: float = 0.0) -> Dict:
        """
        添加视频到草稿

        Args:
            video_paths: 视频文件路径列表
            start_time: 开始时间（秒）

        Returns:
            Dict: 响应信息
        """
        if not self.draft_url:
            raise ValueError("请先调用 create_draft 创建草稿")

        logger.info(f"添加 {len(video_paths)} 个视频到草稿")

        # 构建 video_infos
        video_infos = []
        start_us = int(start_time * 1_000_000)
        cursor_us = start_us
        for video_path in video_paths:
            video_path = Path(video_path)

            # 获取视频时长
            import ffmpeg
            probe = ffmpeg.probe(str(video_path))
            duration_us = self._resolve_video_duration_us(probe)
            if duration_us <= 0:
                raise ValueError(f"无法获取有效视频时长: {video_path}")

            # 转换为 URL
            if self.file_server:
                video_url = self.file_server.get_file_url(video_path)
            else:
                # 如果没有文件服务器，尝试直接使用路径
                video_url = str(video_path.absolute())

            video_infos.append({
                "video_url": video_url,
                "start": cursor_us,
                "end": cursor_us + duration_us
            })
            cursor_us += duration_us

        # 将 video_infos 转换为 JSON 字符串
        video_infos_json = json.dumps(video_infos, ensure_ascii=False)

        result = self._request("/openapi/capcut-mate/v1/add_videos", data={
            "draft_url": self.draft_url,
            "video_infos": video_infos_json
        })
        return result

    def add_video_segments(self, video_path: str, segments: List[Dict]) -> Dict:
        """
        添加视频片段到草稿 (用于去气口处理)

        Args:
            video_path: 视频文件路径
            segments: 片段列表 [{"source_start": 0.0, "source_end": 2.5, "target_start": 0.0}, ...]

        Returns:
            Dict: 响应信息
        """
        if not self.draft_url:
            raise ValueError("请先调用 create_draft 创建草稿")

        logger.info(f"添加 {len(segments)} 个视频片段到草稿")

        # 转换为 URL
        video_path = Path(video_path)
        if self.file_server:
            video_url = self.file_server.get_file_url(video_path)
        else:
            video_url = str(video_path.absolute())

        # 构建 video_infos
        video_infos = []
        for seg in segments:
            # 计算片段时长
            duration = seg["source_end"] - seg["source_start"]

            video_info = {
                "video_url": video_url,
                "start": int(seg["target_start"] * 1_000_000),  # 转换为微秒
                "end": int((seg["target_start"] + duration) * 1_000_000),
                "duration": int(duration * 1_000_000),
                "source_start": int(seg["source_start"] * 1_000_000),  # 原视频中的开始位置
                "source_end": int(seg["source_end"] * 1_000_000)  # 原视频中的结束位置
            }
            video_infos.append(video_info)

        # 将 video_infos 转换为 JSON 字符串
        video_infos_json = json.dumps(video_infos, ensure_ascii=False)

        result = self._request("/openapi/capcut-mate/v1/add_videos", data={
            "draft_url": self.draft_url,
            "video_infos": video_infos_json
        })

        logger.info(f"成功添加 {len(segments)} 个视频片段")
        return result

    def add_background_image(
        self,
        image_path: Union[str, Path],
        width: int,
        height: int,
        duration: float,
        alpha: float = 1.0,
    ) -> Dict:
        """添加一张铺满画布的背景图片。"""
        if not self.draft_url:
            raise ValueError("请先调用 create_draft 创建草稿")

        image_path = Path(image_path)
        if self.file_server:
            image_url = self.file_server.get_file_url(image_path)
        else:
            image_url = str(image_path.absolute())

        image_infos = [{
            "image_url": image_url,
            "width": int(width),
            "height": int(height),
            "start": 0,
            "end": int(max(duration, 0.0) * 1_000_000),
        }]

        logger.info(f"添加背景图片到草稿: {image_path.name}")
        return self._request("/openapi/capcut-mate/v1/add_images", data={
            "draft_url": self.draft_url,
            "image_infos": json.dumps(image_infos, ensure_ascii=False),
            "alpha": alpha,
            "scale_x": 1.0,
            "scale_y": 1.0,
            "transform_x": 0,
            "transform_y": 0,
        })


    def add_audios(self, audio_paths: List[str], start_time: float = 0.0, volume: float = 1.0) -> Dict:
        """
        添加音频到草稿

        Args:
            audio_paths: 音频文件路径列表
            start_time: 开始时间（秒）
            volume: 音量（0.0-2.0）

        Returns:
            Dict: 响应信息
        """
        if not self.draft_url:
            raise ValueError("请先调用 create_draft 创建草稿")

        logger.info(f"添加 {len(audio_paths)} 个音频到草稿")
        start_us = int(start_time * 1_000_000)
        cursor_us = start_us
        audio_infos = []
        for path in audio_paths:
            abs_path = Path(path).absolute()
            if not abs_path.exists():
                logger.warning(f"音频文件不存在，跳过: {abs_path}")
                continue

            import ffmpeg
            probe = ffmpeg.probe(str(abs_path))
            duration = float(probe["format"]["duration"])
            duration_us = int(duration * 1_000_000)

            if self.file_server:
                audio_url = self.file_server.get_file_url(abs_path)
            else:
                audio_url = str(abs_path)

            audio_infos.append({
                "audio_url": audio_url,
                "start": cursor_us,
                "end": cursor_us + duration_us,
                "duration": duration_us,
                "volume": float(volume),
            })
            cursor_us += duration_us

        if not audio_infos:
            logger.warning("没有有效音频可添加")
            return {"code": 0, "message": "没有有效音频可添加"}

        result = self._request("/openapi/capcut-mate/v1/add_audios", data={
            "draft_url": self.draft_url,
            "audio_infos": json.dumps(audio_infos, ensure_ascii=False),
        })
        return result

    def add_bgm_segments(self, bgm_segments, bgm_data, project_root: Path) -> Dict:
        """
        添加多个BGM片段到草稿

        Args:
            bgm_segments: BGM片段列表 (List[BGMSegment])
            bgm_data: BGM配置数据 (BGMData)
            project_root: 项目根目录

        Returns:
            Dict: 响应信息
        """
        if not self.draft_url:
            raise ValueError("请先调用 create_draft 创建草稿")

        logger.info(f"添加 {len(bgm_segments)} 个BGM片段到草稿")

        # 构建 audio_infos
        audio_infos = []
        for segment in bgm_segments:
            # 获取绝对路径
            abs_path = segment.get_absolute_path(project_root)
            if not abs_path.exists():
                raise FileNotFoundError(f"BGM文件不存在: {segment.path} -> {abs_path}")

            # 计算结束时间
            if segment.end is None:
                raise ValueError(f"BGM片段缺少结束时间: path={segment.path}, start={segment.start}")
            end_time = float(segment.end)
            duration = end_time - float(segment.start)
            if duration <= 0:
                raise ValueError(
                    f"BGM片段时长无效: path={segment.path}, start={segment.start}, end={segment.end}"
                )

            # 获取有效音量
            volume = float(bgm_data.get_effective_volume(segment))
            if volume < 0.0 or volume > 2.0:
                raise ValueError(f"BGM音量超出范围(0.0-2.0): {volume}, path={segment.path}")

            # 转换文件路径为 URL（如果有 file_server）
            if self.file_server:
                audio_url = self.file_server.get_file_url(abs_path)
            else:
                audio_url = str(abs_path)

            source_start = float(getattr(segment, "source_start", 0.0) or 0.0)
            source_end_raw = getattr(segment, "source_end", None)
            source_end = source_start + duration if source_end_raw is None else float(source_end_raw)

            audio_info = {
                "audio_url": audio_url,
                "start": int(float(segment.start) * 1_000_000),  # 秒转微秒
                "end": int(end_time * 1_000_000),
                "duration": int(duration * 1_000_000),
                "source_start": int(source_start * 1_000_000),
                "source_end": int(source_end * 1_000_000),
                "volume": volume,
            }
            audio_infos.append(audio_info)
            logger.debug(
                f"BGM片段: {segment.path}, timeline={segment.start:.2f}s-{end_time:.2f}s, "
                f"source={source_start:.2f}s-{source_end:.2f}s, 音量={volume:.2f}"
            )

        if not audio_infos:
            logger.warning("没有有效的BGM片段可添加")
            return {"code": 0, "message": "没有有效的BGM片段"}

        # 将 audio_infos 转换为 JSON 字符串
        audio_infos_json = json.dumps(audio_infos, ensure_ascii=False)

        # 调用 API
        result = self._request("/openapi/capcut-mate/v1/add_audios", data={
            "draft_url": self.draft_url,
            "audio_infos": audio_infos_json
        })

        logger.info(f"成功添加 {len(audio_infos)}/{len(bgm_segments)} 个BGM片段")
        return result

    def add_captions(self, captions: List[Dict], options: Optional[Dict[str, Any]] = None) -> Dict:
        """
        添加字幕到草稿

        Args:
            captions: 字幕列表 [{"start_time": 0.0, "end_time": 1.0, "content": "字幕文本"}]

        Returns:
            Dict: 响应信息
        """
        if not self.draft_url:
            raise ValueError("请先调用 create_draft 创建草稿")

        logger.info(f"添加 {len(captions)} 条字幕到草稿")

        # 将 captions 转换为 JSON 字符串
        captions_json = json.dumps(captions, ensure_ascii=False)

        payload = {
            "draft_url": self.draft_url,
            "captions": captions_json
        }
        if options:
            payload.update(options)

        result = self._request("/openapi/capcut-mate/v1/add_captions", data=payload)
        return result

    def save_draft(self) -> str:
        """
        保存草稿

        Returns:
            str: 草稿保存路径
        """
        if not self.draft_url:
            raise ValueError("请先调用 create_draft 创建草稿")

        logger.info(f"保存草稿: {self.draft_id}")
        result = self._request("/openapi/capcut-mate/v1/save_draft", data={
            "draft_url": self.draft_url
        })

        # 返回 draft_url 作为草稿路径
        logger.info(f"草稿保存成功: {self.draft_url}")

        sync_enabled = self.config.get("sync_to_local_draft", True)
        if sync_enabled:
            try:
                local_draft_dir = self._sync_draft_to_local_root()
                self.local_draft_dir = local_draft_dir
                logger.info(f"草稿已同步到本地剪映目录: {local_draft_dir}")
            except Exception as exc:
                logger.warning(f"草稿同步到本地剪映目录失败: {exc}")
        elif self._is_draft_in_local_root(self.draft_id):
            self.local_draft_dir = self.draft_root / self.draft_id
            logger.info(f"草稿已写入本地剪映目录: {self.draft_root / self.draft_id}")
        else:
            logger.warning(
                "草稿未出现在本地剪映目录，可能仅保存在远端。"
                f" draft_id={self.draft_id}, draft_root={self.draft_root}"
            )
        return self.draft_url

    def get_local_draft_dir(self) -> Optional[Path]:
        """返回当前草稿同步到本机后的目录。"""
        if self.local_draft_dir and self.local_draft_dir.exists():
            return self.local_draft_dir

        if self.draft_id:
            candidate = self.draft_root / self.draft_id
            if candidate.exists():
                self.local_draft_dir = candidate
                return candidate

        return None

    def get_draft_info(self) -> Dict:
        """
        获取草稿信息

        Returns:
            Dict: 草稿信息
        """
        if not self.draft_url:
            raise ValueError("请先调用 create_draft 创建草稿")

        logger.info(f"获取草稿信息: {self.draft_id}")
        result = self._request("/openapi/capcut-mate/v1/get_draft", method="GET", data={
            "draft_id": self.draft_id
        })
        return result

    def add_video_material(
        self,
        video_source: Union[str, Path],
        start_time: float,
        duration: float,
        track_index: int = 2
    ) -> Dict:
        """
        通过URL添加视频素材

        Args:
            video_source: 视频来源（本地路径或远程 URL）
            start_time: 开始时间(秒)
            duration: 持续时间(秒)
            track_index: 轨道索引(默认2,避免与主视频冲突)

        Returns:
            Dict: 响应信息
        """
        if not self.draft_url:
            raise ValueError("请先调用 create_draft 创建草稿")

        video_source = str(video_source)
        logger.info(f"添加视频素材: {video_source[:50]}...")
        try:
            if video_source.startswith("http://") or video_source.startswith("https://"):
                video_url = video_source
            else:
                video_path = Path(video_source).absolute()
                if self.file_server:
                    video_url = self.file_server.get_file_url(video_path)
                else:
                    video_url = str(video_path)

            video_infos = [{
                "video_url": video_url,
                "start": int(start_time * 1_000_000),
                "end": int((start_time + duration) * 1_000_000),
                "duration": int(duration * 1_000_000),
            }]
            result = self._request("/openapi/capcut-mate/v1/add_videos", data={
                "draft_url": self.draft_url,
                "video_infos": json.dumps(video_infos, ensure_ascii=False),
                "track_index": track_index,
            })
            return result
        except Exception as e:
            logger.error(f"添加视频素材失败: {e}")
            return {"code": -1, "message": str(e)}

    def add_image_material(
        self,
        image_source: Union[str, Path],
        start_time: float,
        duration: float = 3.0,
        track_index: int = 2
    ) -> Dict:
        """
        通过URL添加图片素材

        Args:
            image_source: 图片来源（本地路径或远程 URL）
            start_time: 开始时间(秒)
            duration: 持续时间(秒,默认3秒)
            track_index: 轨道索引(默认2,避免与主视频冲突)

        Returns:
            Dict: 响应信息
        """
        if not self.draft_url:
            raise ValueError("请先调用 create_draft 创建草稿")

        image_source = str(image_source)
        logger.info(f"添加图片素材: {image_source[:50]}...")
        try:
            if image_source.startswith("http://") or image_source.startswith("https://"):
                image_url = image_source
            else:
                image_path = Path(image_source).absolute()
                if self.file_server:
                    image_url = self.file_server.get_file_url(image_path)
                else:
                    image_url = str(image_path)

            image_infos = [{
                "image_url": image_url,
                "start": int(start_time * 1_000_000),
                "end": int((start_time + duration) * 1_000_000),
            }]
            result = self._request("/openapi/capcut-mate/v1/add_images", data={
                "draft_url": self.draft_url,
                "image_infos": json.dumps(image_infos, ensure_ascii=False),
                "track_index": track_index,
            })
            return result
        except Exception as e:
            logger.error(f"添加图片素材失败: {e}")
            return {"code": -1, "message": str(e)}
