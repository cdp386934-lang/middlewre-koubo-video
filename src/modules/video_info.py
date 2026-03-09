import ffmpeg
from pathlib import Path
from typing import Dict, Union
from loguru import logger


class VideoInfoExtractor:
    """视频信息提取模块"""

    def __init__(self, config: dict):
        self.config = config

    def extract(self, video_path: Union[str, Path]) -> Dict:
        """
        提取视频元数据

        Args:
            video_path: 视频文件路径

        Returns:
            Dict: 视频信息
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        logger.info(f"提取视频信息: {video_path}")

        try:
            probe = ffmpeg.probe(str(video_path))
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)

            if not video_stream:
                raise ValueError("未找到视频流")

            # 提取关键信息
            width = int(video_stream['width'])
            height = int(video_stream['height'])
            fps = eval(video_stream['r_frame_rate'])  # 例如 "30/1" -> 30.0
            duration = float(probe['format']['duration'])

            video_info = {
                'width': width,
                'height': height,
                'fps': fps,
                'duration': duration,
                'resolution': f"{width}x{height}",
                'codec': video_stream.get('codec_name', 'unknown'),
                'bitrate': int(probe['format'].get('bit_rate', 0))
            }

            logger.info(f"视频信息: {video_info['resolution']} @ {video_info['fps']}fps, {video_info['duration']:.2f}s")
            return video_info

        except Exception as e:
            logger.error(f"提取视频信息失败: {e}")
            raise
