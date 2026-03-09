from loguru import logger
from ..models.subtitle import SubtitleData, SubtitleSegment


class BreathRemovalModule:
    """去气口处理模块"""

    def __init__(self, config: dict):
        self.config = config

    def process(self, subtitle_data: SubtitleData) -> SubtitleData:
        """
        处理字幕中的气口,检测并标记需要移除的间隔段

        Args:
            subtitle_data: 输入字幕数据

        Returns:
            SubtitleData: 处理后的字幕数据
        """
        # 检查是否启用去气口功能
        breath_config = self.config.get("breath_removal", {})
        if not breath_config.get("enabled", True):
            logger.info("去气口功能已禁用,跳过处理")
            return subtitle_data

        if not subtitle_data.segments:
            logger.info("字幕为空,跳过去气口处理")
            return subtitle_data

        # 获取配置参数
        gap_threshold = breath_config.get("gap_threshold", 0.5)
        min_segment_duration = breath_config.get("min_segment_duration", 0.1)

        logger.info(f"开始去气口处理 (间隔阈值: {gap_threshold}秒)")

        # 按时间排序后遍历相邻字幕片段,检测需要压缩的气口间隔
        segments = sorted(subtitle_data.segments, key=lambda segment: (segment.start, segment.end))
        new_segments = []
        removed_count = 0
        total_removed_duration = 0.0

        for i in range(len(segments)):
            # 保留原始片段
            new_segments.append(segments[i])

            # 检查与下一个片段的间隔
            if i < len(segments) - 1:
                gap = segments[i+1].start - segments[i].end

                # 如果间隔大于阈值,创建一个"气口"片段并标记为移除
                if gap >= gap_threshold and gap >= min_segment_duration:
                    breath_segment = SubtitleSegment(
                        id=0,
                        start=segments[i].end,
                        end=segments[i+1].start,
                        text="[BREATH]",
                        keyword="",
                        keywords=[],
                        text_grade=1,
                        video_grade=1,
                        removed=1  # 标记为移除
                    )
                    new_segments.append(breath_segment)
                    removed_count += 1
                    total_removed_duration += gap
                    logger.debug(f"检测到气口: {segments[i].end:.2f}s - {segments[i+1].start:.2f}s (间隔: {gap:.2f}秒)")

        # 重新编号所有片段
        for idx, seg in enumerate(new_segments, start=1):
            seg.id = idx

        # 更新字幕数据
        subtitle_data.segments = new_segments

        logger.info(f"去气口处理完成: 检测到 {removed_count} 个气口,总计移除 {total_removed_duration:.2f} 秒")
        return subtitle_data
