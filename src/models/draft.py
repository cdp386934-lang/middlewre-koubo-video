from typing import Optional

from pydantic import BaseModel


class DraftMetadata(BaseModel):
    """剪映草稿元数据"""
    draft_id: str
    draft_name: str
    draft_path: str
    video_path: str
    duration: float
    resolution: str
    fps: float
    has_subtitles: bool = False
    has_bgm: bool = False
    keyword_count: int = 0
    generated_title: Optional[str] = None
    author_name: Optional[str] = None
    author_identity: Optional[str] = None
