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

    def _resolve_segment_path(self, segment: BGMSegment, index: int) -> str:
        """解析片段音频路径：优先使用 segment.path，否则从 audio_pool 按顺序轮询。"""
        if segment.path:
            return segment.path

        pool = self.bgm_data.audio_pool if self.bgm_data else []
        if not pool:
            raise ValueError(
                "BGM片段未配置 path，且 bgm.audio_pool 为空。请在片段里配置 path 或提供 3-5 首 audio_pool。"
            )
        return pool[index % len(pool)]

    @staticmethod
    def _probe_audio_duration(abs_path: Path) -> float:
        """读取音频时长（秒）。"""
        import ffmpeg

        probe = ffmpeg.probe(str(abs_path))
        duration_str = probe.get("format", {}).get("duration")
        if duration_str in (None, ""):
            raise ValueError(f"无法读取音频时长: {abs_path}")

        duration = float(duration_str)
        if duration <= 0:
            raise ValueError(f"音频时长无效 ({duration}) : {abs_path}")
        return duration

    def _expand_segment_for_duration(
        self,
        segment: BGMSegment,
        target_end: float,
        segment_index: int,
    ) -> List[BGMSegment]:
        """
        将单个配置片段扩展为可直接下发到 add_audios 的片段列表：
        - 音频长于需求：裁剪
        - 音频短于需求：循环铺满并裁剪最后一段
        """
        resolved_path = self._resolve_segment_path(segment, segment_index)
        segment_with_path = BGMSegment(**{**segment.model_dump(), "path": resolved_path})
        abs_path = segment_with_path.get_absolute_path(self.project_root)
        if not abs_path.exists():
            raise FileNotFoundError(f"BGM文件不存在: {resolved_path} -> {abs_path}")

        if target_end <= segment_with_path.start:
            raise ValueError(f"BGM时间段无效: start={segment_with_path.start}, target_end={target_end}, path={resolved_path}")

        audio_duration = self._probe_audio_duration(abs_path)
        source_start = max(float(segment_with_path.source_start or 0.0), 0.0)
        source_end_limit = float(segment_with_path.source_end) if segment_with_path.source_end is not None else audio_duration

        if source_end_limit > audio_duration:
            logger.warning(f"BGM source_end 超出音频时长，自动裁剪: {resolved_path}, source_end={source_end_limit}, audio={audio_duration}")
            source_end_limit = audio_duration
        if source_end_limit <= source_start:
            raise ValueError(
                f"BGM源区间无效: source_start={source_start}, source_end={source_end_limit}, path={resolved_path}"
            )

        loop_unit = source_end_limit - source_start
        expanded_segments: List[BGMSegment] = []
        cursor = segment_with_path.start

        while cursor < target_end:
            remain = target_end - cursor
            current_duration = min(loop_unit, remain)
            expanded_segments.append(
                BGMSegment(
                    path=resolved_path,
                    start=cursor,
                    end=cursor + current_duration,
                    volume=segment_with_path.volume,
                    source_start=source_start,
                    source_end=source_start + current_duration,
                )
            )
            cursor += current_duration

        return expanded_segments

    def get_bgm_segments(self, draft_duration: Optional[float] = None) -> Optional[List[BGMSegment]]:
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

        valid_segments: List[BGMSegment] = []
        for index, segment in enumerate(self.bgm_data.segments):
            try:
                if draft_duration is None:
                    resolved_path = self._resolve_segment_path(segment, index)
                    segment_with_path = BGMSegment(**{**segment.model_dump(), "path": resolved_path})
                    abs_path = segment_with_path.get_absolute_path(self.project_root)
                    if not abs_path.exists():
                        raise FileNotFoundError(f"BGM文件不存在: {resolved_path} -> {abs_path}")
                    valid_segments.append(segment_with_path)
                    continue

                segment_end = float(segment.end) if segment.end is not None else float(draft_duration)
                effective_end = min(segment_end, float(draft_duration))
                if effective_end <= segment.start:
                    logger.warning(
                        f"BGM片段超出草稿时长，已跳过: path={segment.path}, start={segment.start}, "
                        f"end={segment.end}, draft_duration={draft_duration}"
                    )
                    continue

                valid_segments.extend(self._expand_segment_for_duration(segment, effective_end, segment_index=index))
            except Exception as e:
                raise ValueError(f"处理BGM配置失败 ({segment.path}): {e}") from e

        if not valid_segments:
            logger.warning("没有有效的BGM片段")
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
