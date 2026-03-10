import json
import os
import re
from typing import Any, Dict, List

from loguru import logger
from openai import OpenAI

from ..models.keyword import Keyword, KeywordData


class DeepSeekService:
    """DeepSeek AI 服务"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config["deepseek"]
        api_key = self.config["api_key"]

        # 支持从环境变量读取
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.getenv(env_var)

        if not api_key:
            raise ValueError("DeepSeek API Key 未配置")

        self.client = OpenAI(
            api_key=api_key,
            base_url=self.config["base_url"]
        )
        logger.info("DeepSeek AI 服务初始化完成")

    def _chat(self, prompt: str, temperature: float = None, max_tokens: int = None, system_message: str = None) -> str:
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.config.get("model", "deepseek-chat"),
            messages=messages,
            temperature=self.config.get("temperature", 0.7) if temperature is None else temperature,
            max_tokens=self.config.get("max_tokens", 2000) if max_tokens is None else max_tokens
        )
        return response.choices[0].message.content.strip()

    @staticmethod
    def _strip_code_block(content: str) -> str:
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        return content

    def extract_keywords(self, text: str) -> List[Keyword]:
        """
        从文本中提取关键词

        Args:
            text: 输入文本

        Returns:
            List[Keyword]: 关键词列表
        """
        logger.info(f"开始提取关键词（文本长度: {len(text)} 字）...")

        def split_sentences(raw_text: str) -> List[str]:
            # 兼容中文口播字幕常见分隔符，保留非空句
            parts = re.split(r"[。！？!?；;\n\r]+", raw_text)
            return [part.strip(" ，,。.!?！？；;：:") for part in parts if part and part.strip(" ，,。.!?！？；;：:")]

        def local_fallback_keywords(sentences: List[str]) -> List[Keyword]:
            # 兜底策略：每句取 1-2 个长度 2-6 的候选短语，保证逐句有覆盖
            stop_words = {"我们", "你们", "他们", "这个", "那个", "就是", "然后", "因为", "所以", "但是", "如果", "不是"}
            seen = set()
            collected: List[Keyword] = []

            for sentence in sentences:
                # 先取连续中文片段（2-6字）作为候选
                candidates = re.findall(r"[\u4e00-\u9fff]{2,6}", sentence)
                # 长度优先，其次出现顺序优先
                ranked = sorted(
                    (c for c in candidates if c not in stop_words),
                    key=lambda item: (-len(item), sentence.find(item))
                )
                picked = []
                for word in ranked:
                    if word in picked:
                        continue
                    picked.append(word)
                    if len(picked) >= 2:
                        break
                if not picked:
                    continue

                for word in picked:
                    if word in seen:
                        continue
                    seen.add(word)
                    collected.append(Keyword(word=word, importance=0.8))
            return collected

        sentences = split_sentences(text)
        numbered_sentences = "\n".join(
            f"{idx + 1}. {sentence}" for idx, sentence in enumerate(sentences)
        )

        # 构建提示词：要求逐句返回 1-2 个关键词
        prompt = f"""请按句提取口播字幕关键词，确保每句都有 1-2 个关键词。

要求：
1. 输入是多句字幕，你必须逐句处理
2. 每句只提取 1-2 个关键词
3. 关键词优先名词/动词，避免语气词、虚词
4. 关键词长度建议 2-6 个中文字符
5. 只输出 JSON，不要解释，不要 markdown 代码块

输出格式（严格遵守）：
[
  {{"sentence_index": 1, "keywords": ["关键词1", "关键词2"]}},
  {{"sentence_index": 2, "keywords": ["关键词1"]}}
]

字幕内容：
{numbered_sentences}
"""

        try:
            # 使用专业的 system message
            system_message = "你是专业的中文口播字幕关键词提取助手，严格按句返回每句1-2个关键词。"

            content = self._chat(
                prompt,
                temperature=0.3,  # 降低温度以获得更稳定的输出
                max_tokens=1200,
                system_message=system_message
            )

            keywords: List[Keyword] = []
            stop_words = {"人", "事", "时候", "东西", "地方", "问题", "方面", "情况"}
            seen_words = set()

            cleaned = self._strip_code_block(content).strip()
            parsed_items = json.loads(cleaned) if cleaned else []
            if not isinstance(parsed_items, list):
                parsed_items = []

            for item in parsed_items:
                if not isinstance(item, dict):
                    continue
                sentence_keywords = item.get("keywords", [])
                if not isinstance(sentence_keywords, list):
                    continue

                valid_words = []
                for raw_word in sentence_keywords:
                    word = str(raw_word).strip().strip("\"'“”‘’")
                    if not word:
                        continue
                    if word in stop_words:
                        continue
                    if not (2 <= len(word) <= 6):
                        continue
                    if word in valid_words:
                        continue
                    valid_words.append(word)
                    if len(valid_words) >= 2:
                        break

                for word in valid_words:
                    if word in seen_words:
                        continue
                    seen_words.add(word)
                    keywords.append(Keyword(word=word, importance=0.8))

            # 模型返回不规范时，启用本地兜底
            if not keywords:
                keywords = local_fallback_keywords(sentences)

            logger.info(f"关键词提取完成，共 {len(keywords)} 个关键词")
            return keywords

        except Exception as e:
            logger.error(f"关键词提取失败: {e}")
            import traceback
            traceback.print_exc()
            return local_fallback_keywords(sentences)

    def generate_broll_queries(self, keyword: str, context: str) -> List[str]:
        """根据关键词和上下文生成适用于 Pexels 的英文检索词。"""
        broll_config = self.config.get("broll_query", {})
        fallback_count = int(broll_config.get("fallback_count", 3))
        keyword = (keyword or "").strip()
        context = (context or "").strip()

        if not keyword:
            return []

        fallback_queries = [
            f"{keyword} cinematic b roll",
            f"{keyword} clean background shot",
            f"{keyword} slow motion detail",
        ][:fallback_count]

        prompt_template = broll_config.get("prompt_template")
        if prompt_template:
            prompt = prompt_template.format(keyword=keyword, context=context or keyword)
        else:
            prompt = (
                "Generate exactly 3 English Pexels B-roll search queries as JSON array. "
                f"keyword: {keyword}; context: {context or keyword}. "
                "Prefer clean HD shots, no text/no watermark, medium/close/establishing/slow-motion."
            )

        try:
            content = self._chat(
                prompt,
                temperature=broll_config.get("temperature", 0.2),
                max_tokens=broll_config.get("max_tokens", 220),
                system_message="You generate concise English Pexels search queries for talking-head B-roll."
            )
            cleaned = self._strip_code_block(content).strip()
            parsed = json.loads(cleaned) if cleaned else []
            if not isinstance(parsed, list):
                return fallback_queries

            queries: List[str] = []
            seen = set()
            for item in parsed:
                q = str(item).strip().strip("\"'“”‘’")
                if not q:
                    continue
                normalized = q.lower()
                if normalized in seen:
                    continue
                seen.add(normalized)
                queries.append(q)
                if len(queries) >= 3:
                    break

            return queries or fallback_queries
        except Exception as exc:
            logger.warning(f"B-roll 查询词生成失败，使用兜底关键词: {exc}")
            return fallback_queries

    def generate_title(self, text: str) -> str:
        """根据视频字幕内容生成适合口播封面的短标题。"""
        title_config = self.config.get("title", {})
        max_length = int(title_config.get("max_length", 18))

        prompt = f"""请根据下面这段口播字幕，生成一个适合短视频剪映草稿封面/标题条展示的中文标题。

要求：
1. 只输出 1 个标题，不要解释
2. 标题要像短视频口播标题，吸引点击，但不要夸张低俗
3. 长度控制在 {max_length} 个中文字符以内
4. 不要使用书名号、引号、emoji、换行

字幕内容：
{text}
"""

        try:
            title = self._chat(
                prompt,
                temperature=title_config.get("temperature", 0.8),
                max_tokens=title_config.get("max_tokens", 80)
            )
            title = self._strip_code_block(title).replace("\n", "").strip().strip('"“”')
            if len(title) > max_length:
                title = title[:max_length]
            logger.info(f"标题生成完成: {title}")
            return title
        except Exception as e:
            logger.error(f"标题生成失败: {e}")
            fallback = text.split("。", 1)[0].replace(" ", "")[:max_length]
            logger.info(f"使用降级标题: {fallback}")
            return fallback
