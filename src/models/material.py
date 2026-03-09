"""
素材数据模型
"""
from typing import List, Optional
from pydantic import BaseModel


class Material(BaseModel):
    """单个素材"""
    id: int                          # Pexels素材ID
    type: str                        # "video" 或 "photo"
    keyword: str                     # 搜索关键词
    url: str                         # Pexels页面URL
    download_url: str                # 直接下载URL
    width: int
    height: int
    duration: Optional[float] = None # 视频时长(秒)
    photographer: str                # 作者名
    photographer_url: str            # 作者链接
    segment_id: Optional[int] = None # 对应的字幕segment ID


class MaterialData(BaseModel):
    """素材数据集合"""
    materials: List[Material] = []

    def get_materials_by_keyword(self, keyword: str) -> List[Material]:
        """
        获取指定关键词的所有素材

        Args:
            keyword: 关键词

        Returns:
            素材列表
        """
        return [m for m in self.materials if m.keyword == keyword]

    def get_materials_by_segment(self, segment_id: int) -> List[Material]:
        """
        获取指定字幕segment的所有素材

        Args:
            segment_id: 字幕segment ID

        Returns:
            素材列表
        """
        return [m for m in self.materials if m.segment_id == segment_id]
