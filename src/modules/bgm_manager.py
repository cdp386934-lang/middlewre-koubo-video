from pathlib import Path
from typing import Optional, List
from loguru import logger
from ..models.bgm import BGMSegment, BGMData


class BGMManager:
    """背景音乐管理模块"""

    def __init__(self, config: dict):
        self.config = config
        self.project_root = Path(config["paths"]["input"]).parent
        self.bgm_data = self._load_bgm_config()

    def _load_bgm_config(self) -> Optional[BGMData]:
        """
        从配置中加载BGM配置

        Returns:
            Optional[BGMData]: BGM配置数据，如果没有配置则返回None
        """
        bgm_config = self.config.get("bgm")
        if not bgm_config:
            logger.debug("配置中没有BGM配置")
            return None

        try:
            bgm_data = BGMData(**bgm_config)
            logger.info(f"成功加载BGM配置: {len(bgm_data.segments)} 个片段")
            return bgm_data
        except Exception as e:
            logger.error(f"加载BGM配置失败: {e}")
            return None

    def get_bgm_segments(self) -> Optional[List[BGMSegment]]:
        """
        获取验证后的BGM片段列表

        Returns:
            Optional[List[BGMSegment]]: BGM片段列表，如果没有有效片段则返回None
        """
        if not self.bgm_data or not self.bgm_data.enabled:
            logger.info("BGM功能未启用")
            return None

        if not self.bgm_data.segments:
            logger.info("没有配置BGM片段")
            return None

        # 验证所有片段的文件是否存在
        valid_segments = []
        for segment in self.bgm_data.segments:
            abs_path = segment.get_absolute_path(self.project_root)
            if not abs_path.exists():
                logger.warning(f"BGM文件不存在，跳过: {segment.path}")
                continue
            valid_segments.append(segment)

        if not valid_segments:
            logger.warning("没有有效的BGM片段（所有文件都不存在）")
            return None

        logger.info(f"找到 {len(valid_segments)} 个有效的BGM片段")
        return valid_segments

    def get_bgm_data(self) -> Optional[BGMData]:
        """
        获取完整的BGM配置数据

        Returns:
            Optional[BGMData]: BGM配置数据
        """
        return self.bgm_data

    def get_bgm(self, bgm_name: Optional[str] = None) -> Optional[Path]:
        """
        获取背景音乐（向后兼容的旧方法）

        Args:
            bgm_name: 背景音乐名称（可选）

        Returns:
            Optional[Path]: 第一个BGM片段的路径，如果没有则返回None
        """
        segments = self.get_bgm_segments()
        if not segments:
            return None

        # 返回第一个片段的路径（向后兼容）
        first_segment = segments[0]
        abs_path = first_segment.get_absolute_path(self.project_root)
        logger.info(f"返回第一个BGM片段路径（兼容模式）: {abs_path}")
        return abs_path
