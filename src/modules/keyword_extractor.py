from pathlib import Path
from typing import Union

from loguru import logger

from ..services.deepseek_service import DeepSeekService
from ..models.subtitle import SubtitleData
from ..models.keyword import KeywordData
from ..utils.file_handler import write_json


class KeywordExtractor:
    """关键词提取模块"""

    def __init__(self, config: dict):
        self.config = config
        self.deepseek_service = DeepSeekService(config)

    def extract(self, subtitle_data: SubtitleData, output_path: Union[str, Path] = None) -> KeywordData:
        """
        从字幕中提取关键词

        Args:
            subtitle_data: 输入字幕数据
            output_path: 输出关键词路径（可选）

        Returns:
            KeywordData: 关键词数据
        """
        # 获取完整文本
        full_text = subtitle_data.get_full_text()
        logger.info(f"开始提取关键词，文本长度: {len(full_text)}")

        # 调用 AI 提取关键词
        keywords = self._normalize_keywords(self.deepseek_service.extract_keywords(full_text))

        # 在字幕中匹配关键词位置，并补齐 auto_jianying 风格的 keyword / grade 信息
        self._annotate_segments(subtitle_data, keywords)

        keyword_data = KeywordData(keywords=keywords)

        # 保存关键词文件
        if output_path is None:
            keyword_dir = Path(self.config["paths"]["keywords"])
            keyword_dir.mkdir(parents=True, exist_ok=True)
            output_path = keyword_dir / "keywords.json"
        else:
            output_path = Path(output_path)

        write_json(keyword_data.model_dump(), output_path)
        logger.info(f"关键词文件已保存: {output_path}")

        return keyword_data

    def _normalize_keywords(self, keywords):
        """清洗并裁剪 AI 返回的关键词。"""
        max_count = self.config.get("keyword", {}).get("max_count")
        seen_words = set()
        normalized_keywords = []

        for keyword in keywords:
            word = keyword.word.strip()
            if not word or word in seen_words:
                continue

            keyword.word = word
            keyword.positions = []
            keyword.frequency = 0
            normalized_keywords.append(keyword)
            seen_words.add(word)

            if max_count and len(normalized_keywords) >= max_count:
                break

        return normalized_keywords

    def _annotate_segments(self, subtitle_data: SubtitleData, keywords) -> None:
        """按 auto_jianying 的思路给字幕补齐关键词和等级。"""
        for segment in subtitle_data.segments:
            segment.keywords = []
            segment.keyword = ""
            segment.text_grade = 1
            segment.video_grade = 1

            if segment.removed == 1:
                continue

            for keyword in keywords:
                if keyword.word not in segment.text:
                    continue

                keyword.positions.append(segment.id)
                keyword.frequency += segment.text.count(keyword.word)

                if keyword.word not in segment.keywords:
                    segment.keywords.append(keyword.word)

            primary_keyword = self._pick_primary_keyword(segment.text, segment.keywords)
            if not primary_keyword:
                continue

            segment.keyword = primary_keyword
            if primary_keyword == segment.text:
                segment.text_grade = 3
                segment.video_grade = 2
            else:
                segment.text_grade = 2

    @staticmethod
    def _pick_primary_keyword(text: str, matched_keywords) -> str:
        """复用 auto_jianying 的主关键词判定：命中整句时返回整句。"""
        for keyword in matched_keywords:
            if keyword not in text:
                continue

            if len(keyword) + 2 > len(text):
                return text

            return keyword

        return ""
