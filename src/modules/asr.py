from pathlib import Path
from typing import Union
from loguru import logger
from ..services.whisper_service import WhisperService
from ..models.subtitle import SubtitleData
from ..utils.file_handler import write_json


class ASRModule:
    """音频转文字模块"""

    def __init__(self, config: dict):
        self.config = config
        self.whisper_service = WhisperService(config)

    def transcribe(self, audio_path: Union[str, Path], output_path: Union[str, Path] = None) -> SubtitleData:
        """
        将音频转换为字幕

        Args:
            audio_path: 输入音频路径
            output_path: 输出字幕路径（可选）

        Returns:
            SubtitleData: 字幕数据
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        # 执行 ASR
        subtitle_data = self.whisper_service.transcribe(audio_path)

        # 保存字幕文件
        if output_path is None:
            subtitle_dir = Path(self.config["paths"]["subtitles"])
            subtitle_dir.mkdir(parents=True, exist_ok=True)
            output_path = subtitle_dir / f"{audio_path.stem}.json"
        else:
            output_path = Path(output_path)

        write_json(subtitle_data.model_dump(), output_path)
        logger.info(f"字幕文件已保存: {output_path}")

        return subtitle_data
