import whisper
from pathlib import Path
from typing import Dict, Any, Union
from loguru import logger
from ..models.subtitle import SubtitleData, SubtitleSegment


class WhisperService:
    """Whisper ASR 服务"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config["whisper"]
        self.model = None
        logger.info(f"初始化 Whisper 服务，模型大小: {self.config['model_size']}")

    def load_model(self):
        """加载 Whisper 模型"""
        if self.model is None:
            logger.info("正在加载 Whisper 模型...")
            self.model = whisper.load_model(
                self.config["model_size"],
                device=self.config.get("device", "cpu")
            )
            logger.info("Whisper 模型加载完成")

    def transcribe(self, audio_path: Union[str, Path]) -> SubtitleData:
        """
        转录音频文件为字幕

        Args:
            audio_path: 音频文件路径

        Returns:
            SubtitleData: 字幕数据
        """
        self.load_model()

        logger.info(f"开始转录音频: {audio_path}")
        result = self.model.transcribe(
            str(audio_path),
            language=self.config.get("language", "zh"),
            word_timestamps=self.config.get("word_timestamps", True),
            verbose=False
        )

        # 转换为字幕数据
        segments = []
        for i, segment in enumerate(result["segments"]):
            segments.append(SubtitleSegment(
                id=i + 1,
                start=segment["start"],
                end=segment["end"],
                text=segment["text"].strip()
            ))

        subtitle_data = SubtitleData(
            segments=segments,
            language=self.config.get("language", "zh"),
            duration=result.get("duration", 0.0)
        )

        logger.info(f"转录完成，共 {len(segments)} 个字幕片段")
        return subtitle_data
