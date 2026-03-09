import ffmpeg
from pathlib import Path
from typing import Union
from loguru import logger


class VideoToAudioConverter:
    """视频转音频模块"""

    def __init__(self, config: dict):
        self.config = config

    def convert(self, video_path: Union[str, Path], output_path: Union[str, Path] = None) -> Path:
        """
        将视频转换为音频

        Args:
            video_path: 输入视频路径
            output_path: 输出音频路径（可选）

        Returns:
            Path: 输出音频路径
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        # 默认输出路径
        if output_path is None:
            audio_dir = Path(self.config["paths"]["audio"])
            audio_dir.mkdir(parents=True, exist_ok=True)
            output_path = audio_dir / f"{video_path.stem}.wav"
        else:
            output_path = Path(output_path)

        logger.info(f"开始转换视频为音频: {video_path} -> {output_path}")

        try:
            # 使用 ffmpeg 提取音频
            stream = ffmpeg.input(str(video_path))
            stream = ffmpeg.output(stream, str(output_path),
                                 acodec='pcm_s16le',  # WAV 格式
                                 ac=1,                 # 单声道
                                 ar='16000')           # 16kHz 采样率
            ffmpeg.run(stream, overwrite_output=True, quiet=True)

            logger.info(f"音频转换完成: {output_path}")
            return output_path

        except ffmpeg.Error as e:
            logger.error(f"音频转换失败: {e}")
            raise
