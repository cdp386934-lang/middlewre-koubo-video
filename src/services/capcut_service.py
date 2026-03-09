import requests
import json
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from urllib.parse import urlparse, parse_qs
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
        logger.info(f"草稿创建成功: {self.draft_id}")
        return self.draft_id

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
        for video_path in video_paths:
            video_path = Path(video_path)

            # 获取视频时长
            import ffmpeg
            probe = ffmpeg.probe(str(video_path))
            duration = float(probe['format']['duration'])

            # 转换为 URL
            if self.file_server:
                video_url = self.file_server.get_file_url(video_path)
            else:
                # 如果没有文件服务器，尝试直接使用路径
                video_url = str(video_path.absolute())

            video_infos.append({
                "video_url": video_url,
                "start": start_time,
                "end": start_time + duration
            })

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


    def add_audios(self, audio_paths: List[str], start_time: float = 0.0, volume: float = 1.0) -> Dict:
        """
        添加音频到草稿

        Args:
            audio_paths: 音频文件路径列表
            start_time: 开始时间（秒）
            volume: 音量（0-1）

        Returns:
            Dict: 响应信息
        """
        if not self.draft_url:
            raise ValueError("请先调用 create_draft 创建草稿")

        logger.info(f"添加 {len(audio_paths)} 个音频到草稿")
        result = self._request("/openapi/capcut-mate/v1/add_audios", data={
            "draft_url": self.draft_url,
            "audio_paths": [str(Path(p).absolute()) for p in audio_paths],
            "start_time": start_time,
            "volume": volume
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
        success_count = 0

        for segment in bgm_segments:
            try:
                # 获取绝对路径
                abs_path = segment.get_absolute_path(project_root)
                if not abs_path.exists():
                    logger.warning(f"BGM文件不存在，跳过: {segment.path}")
                    continue

                # 使用 ffmpeg 探测音频时长
                import ffmpeg
                probe = ffmpeg.probe(str(abs_path))
                audio_duration = float(probe['format']['duration'])

                # 计算结束时间
                if segment.end is None:
                    # 如果没有指定结束时间，则播放到音频文件结束
                    end_time = segment.start + audio_duration
                else:
                    end_time = segment.end

                # 计算实际播放时长
                duration = end_time - segment.start

                # 获取有效音量
                volume = bgm_data.get_effective_volume(segment)

                # 转换文件路径为 URL（如果有 file_server）
                if self.file_server:
                    audio_url = self.file_server.get_file_url(abs_path)
                else:
                    audio_url = str(abs_path)

                # 构建音频信息
                audio_info = {
                    "audio_url": audio_url,
                    "start": int(segment.start * 1_000_000),      # 秒转微秒
                    "end": int(end_time * 1_000_000),
                    "duration": int(duration * 1_000_000),
                    "volume": volume
                }
                audio_infos.append(audio_info)
                success_count += 1

                logger.debug(f"BGM片段: {segment.path}, 时间: {segment.start:.2f}s-{end_time:.2f}s, 音量: {volume}")

            except Exception as e:
                logger.error(f"处理BGM片段失败 ({segment.path}): {e}")
                continue

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

        logger.info(f"成功添加 {success_count}/{len(bgm_segments)} 个BGM片段")
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
        if self._is_draft_in_local_root(self.draft_id):
            logger.info(f"草稿已写入本地剪映目录: {self.draft_root / self.draft_id}")
        else:
            logger.warning(
                "草稿未出现在本地剪映目录，可能仅保存在远端。"
                f" draft_id={self.draft_id}, draft_root={self.draft_root}"
            )
        return self.draft_url

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
        draft_id: str,
        video_url: str,
        start_time: float,
        duration: float,
        track_index: int = 2
    ) -> Dict:
        """
        通过URL添加视频素材

        Args:
            draft_id: 草稿ID
            video_url: 视频URL
            start_time: 开始时间(秒)
            duration: 持续时间(秒)
            track_index: 轨道索引(默认2,避免与主视频冲突)

        Returns:
            Dict: 响应信息
        """
        logger.info(f"添加视频素材: {video_url[:50]}...")
        try:
            result = self._request("/openapi/capcut-mate/v1/add_videos", data={
                "draft_id": draft_id,
                "video_url": video_url,
                "track_index": track_index,
                "start_time": int(start_time * 1000000),  # 转换为微秒
                "duration": int(duration * 1000000)
            })
            return result
        except Exception as e:
            logger.error(f"添加视频素材失败: {e}")
            return {"code": -1, "message": str(e)}

    def add_image_material(
        self,
        draft_id: str,
        image_url: str,
        start_time: float,
        duration: float = 3.0,
        track_index: int = 2
    ) -> Dict:
        """
        通过URL添加图片素材

        Args:
            draft_id: 草稿ID
            image_url: 图片URL
            start_time: 开始时间(秒)
            duration: 持续时间(秒,默认3秒)
            track_index: 轨道索引(默认2,避免与主视频冲突)

        Returns:
            Dict: 响应信息
        """
        logger.info(f"添加图片素材: {image_url[:50]}...")
        try:
            result = self._request("/openapi/capcut-mate/v1/add_images", data={
                "draft_id": draft_id,
                "image_url": image_url,
                "track_index": track_index,
                "start_time": int(start_time * 1000000),  # 转换为微秒
                "duration": int(duration * 1000000)
            })
            return result
        except Exception as e:
            logger.error(f"添加图片素材失败: {e}")
            return {"code": -1, "message": str(e)}
