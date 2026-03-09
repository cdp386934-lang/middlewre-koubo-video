from pathlib import Path
from typing import Dict, Any, Union
from loguru import logger
from .modules.video_to_audio import VideoToAudioConverter
from .modules.asr import ASRModule
from .modules.breath_removal import BreathRemovalModule
from .modules.keyword_extractor import KeywordExtractor
from .modules.material_manager import MaterialManager
from .modules.bgm_manager import BGMManager
from .modules.video_info import VideoInfoExtractor
from .modules.draft_generator import DraftGenerator
from .models.draft import DraftMetadata
from .services.deepseek_service import DeepSeekService
from .utils.file_handler import write_json


class VideoPipeline:
    """视频处理工作流编排器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # 初始化各个模块
        self.video_to_audio = VideoToAudioConverter(config)
        self.asr_module = ASRModule(config)
        self.breath_removal = BreathRemovalModule(config)
        self.keyword_extractor = KeywordExtractor(config)
        self.deepseek_service = DeepSeekService(config)
        self.material_manager = MaterialManager(config)
        self.bgm_manager = BGMManager(config)
        self.video_info_extractor = VideoInfoExtractor(config)
        self.draft_generator = DraftGenerator(config)

        logger.info("视频处理工作流初始化完成")

    def run(self, input_video_path: Union[str, Path]) -> DraftMetadata:
        """
        执行完整的视频处理工作流

        Args:
            input_video_path: 输入视频路径

        Returns:
            DraftMetadata: 草稿元数据
        """
        input_video_path = Path(input_video_path)
        if not input_video_path.exists():
            raise FileNotFoundError(f"输入视频不存在: {input_video_path}")

        logger.info(f"=" * 60)
        logger.info(f"开始处理视频: {input_video_path.name}")
        logger.info(f"=" * 60)

        # 步骤1: 视频转音频
        logger.info("[步骤 1/8] 视频转音频")
        audio_path = self.video_to_audio.convert(input_video_path)

        # 步骤2: 音频转文字
        logger.info("[步骤 2/8] 音频转文字 (ASR)")
        subtitle_data = self.asr_module.transcribe(audio_path)

        # 步骤3: 去气口处理
        logger.info("[步骤 3/8] 去气口处理")
        subtitle_data = self.breath_removal.process(subtitle_data)
        self._save_processed_subtitles(audio_path, subtitle_data)

        # 步骤4: 关键词提取
        logger.info("[步骤 4/8] 关键词提取")
        keyword_data = self.keyword_extractor.extract(subtitle_data)
        self._save_processed_subtitles(audio_path, subtitle_data)

        logger.info("[步骤 4.5/8] 生成标题")
        generated_title = self.deepseek_service.generate_title(subtitle_data.get_full_text())

        # 步骤5: 素材管理
        logger.info("[步骤 5/8] 素材管理")
        material_data = None
        if self.config.get("pexels", {}).get("enabled", True):
            material_data = self.material_manager.manage(subtitle_data, keyword_data)
        else:
            logger.info("素材管理已禁用")

        # 步骤6: 背景音乐（可选）
        logger.info("[步骤 6/8] 背景音乐")
        bgm_segments = self.bgm_manager.get_bgm_segments()
        bgm_data = self.bgm_manager.get_bgm_data()

        # 步骤7: 视频信息
        logger.info("[步骤 7/8] 提取视频信息")
        video_info = self.video_info_extractor.extract(input_video_path)

        # 步骤8: 生成剪映草稿
        logger.info("[步骤 8/8] 生成剪映草稿")
        draft_metadata = self.draft_generator.generate(
            input_video_path,
            subtitle_data,
            keyword_data,
            video_info,
            bgm_path=None,              # 旧参数设为 None
            bgm_segments=bgm_segments,  # 新参数
            bgm_data=bgm_data,          # 新参数
            material_data=material_data,
            generated_title=generated_title,
        )

        logger.info(f"=" * 60)
        logger.info(f"处理完成！")
        logger.info(f"草稿 ID: {draft_metadata.draft_id}")
        logger.info(f"草稿路径: {draft_metadata.draft_path}")
        logger.info(f"=" * 60)

        return draft_metadata

    def _save_processed_subtitles(self, audio_path: Path, subtitle_data) -> None:
        """覆盖保存处理后的字幕，便于后续人工复查。"""
        subtitle_dir = Path(self.config["paths"]["subtitles"])
        subtitle_dir.mkdir(parents=True, exist_ok=True)
        output_path = subtitle_dir / f"{audio_path.stem}.json"
        write_json(subtitle_data.model_dump(), output_path)
        logger.info(f"更新字幕文件: {output_path}")
