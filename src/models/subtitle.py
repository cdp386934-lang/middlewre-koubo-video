from typing import List

from pydantic import BaseModel, Field


class SubtitleSegment(BaseModel):
    """单个字幕片段"""
    id: int
    start: float  # 开始时间（秒）
    end: float    # 结束时间（秒）
    text: str     # 字幕文本
    keyword: str = ""  # auto_jianying 风格的主关键词
    keywords: List[str] = Field(default_factory=list)  # 该片段中的关键词列表
    text_grade: int = 1  # 字幕等级（1=普通, 2=关键词高亮, 3=整句重点）
    video_grade: int = 1  # 视频等级（1=普通, 2=重点镜头）
    removed: int = 0  # 是否被去气口处理移除（0=保留, 1=移除）


class SubtitleData(BaseModel):
    """完整字幕数据"""
    segments: List[SubtitleSegment]
    language: str = "zh"
    duration: float = 0.0  # 总时长（秒）

    def get_full_text(self) -> str:
        """获取完整文本（不包含被移除的片段）"""
        return " ".join([seg.text for seg in self.segments if seg.removed == 0])

    def to_srt(self) -> str:
        """转换为 SRT 格式"""
        srt_lines = []
        for seg in self.segments:
            if seg.removed == 1:
                continue
            srt_lines.append(f"{seg.id}")
            srt_lines.append(f"{self._format_time(seg.start)} --> {self._format_time(seg.end)}")
            srt_lines.append(seg.text)
            srt_lines.append("")
        return "\n".join(srt_lines)

    @staticmethod
    def _format_time(seconds: float) -> str:
        """格式化时间为 SRT 格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
