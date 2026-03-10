from pydantic import BaseModel, field_validator
from typing import List, Optional
from pathlib import Path


class BGMSegment(BaseModel):
    """单个背景音乐片段"""
    path: Optional[str] = None           # 音频文件路径（可选：未设置时由 audio_pool 自动分配）
    start: float                        # 开始时间（秒）
    end: Optional[float] = None         # 结束时间（秒，None=播放完整音频）
    volume: Optional[float] = None      # 音量（0.0-2.0，None=使用默认值）
    source_start: float = 0.0           # 源音频开始时间（秒）
    source_end: Optional[float] = None  # 源音频结束时间（秒，None=到文件结尾）

    @field_validator('end')
    @classmethod
    def validate_end_time(cls, v, info):
        """验证结束时间必须大于开始时间"""
        if v is not None and 'start' in info.data:
            start = info.data['start']
            if v <= start:
                raise ValueError(f"结束时间 ({v}) 必须大于开始时间 ({start})")
        return v

    @field_validator('volume')
    @classmethod
    def validate_volume(cls, v):
        """验证音量范围"""
        if v is not None and (v < 0.0 or v > 2.0):
            raise ValueError(f"音量 ({v}) 必须在 0.0-2.0 范围内")
        return v

    @field_validator('source_start')
    @classmethod
    def validate_source_start(cls, v):
        """验证源音频开始时间"""
        if v < 0:
            raise ValueError(f"source_start ({v}) 不能小于 0")
        return v

    @field_validator('source_end')
    @classmethod
    def validate_source_end(cls, v, info):
        """验证源音频结束时间必须大于源开始时间"""
        if v is not None and 'source_start' in info.data:
            source_start = info.data['source_start']
            if v <= source_start:
                raise ValueError(f"source_end ({v}) 必须大于 source_start ({source_start})")
        return v

    def get_absolute_path(self, project_root: Path) -> Path:
        """
        转换相对路径为绝对路径

        Args:
            project_root: 项目根目录

        Returns:
            Path: 绝对路径
        """
        if not self.path:
            raise ValueError("BGM片段缺少 path，且未能从 audio_pool 分配")

        path = Path(self.path)
        if path.is_absolute():
            return path
        else:
            return (project_root / path).resolve()


class BGMData(BaseModel):
    """背景音乐配置数据"""
    enabled: bool = True
    default_volume: float = 0.3
    audio_pool: List[str] = []          # 可选音频池（建议 3-5 首）
    segments: List[BGMSegment] = []

    @field_validator('default_volume')
    @classmethod
    def validate_default_volume(cls, v):
        """验证默认音量范围"""
        if v < 0.0 or v > 2.0:
            raise ValueError(f"默认音量 ({v}) 必须在 0.0-2.0 范围内")
        return v

    def get_effective_volume(self, segment: BGMSegment) -> float:
        """
        获取片段的有效音量

        Args:
            segment: BGM片段

        Returns:
            float: 有效音量（片段音量或默认音量）
        """
        return segment.volume if segment.volume is not None else self.default_volume
