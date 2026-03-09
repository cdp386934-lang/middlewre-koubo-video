from typing import List

from pydantic import BaseModel, Field


class Keyword(BaseModel):
    """关键词"""
    word: str           # 关键词文本
    importance: float   # 重要性（0-1）
    frequency: int = 0  # 出现频率
    positions: List[int] = Field(default_factory=list)  # 出现在哪些字幕片段中（segment id）


class KeywordData(BaseModel):
    """关键词数据集合"""
    keywords: List[Keyword]

    def get_top_keywords(self, n: int = 10) -> List[Keyword]:
        """获取前 N 个最重要的关键词"""
        sorted_keywords = sorted(self.keywords, key=lambda k: k.importance, reverse=True)
        return sorted_keywords[:n]
