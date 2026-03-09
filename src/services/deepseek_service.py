import json
import os
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

    def _chat(self, prompt: str, temperature: float = None, max_tokens: int = None) -> str:
        response = self.client.chat.completions.create(
            model=self.config.get("model", "deepseek-chat"),
            messages=[
                {"role": "user", "content": prompt}
            ],
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
        logger.info("开始提取关键词...")

        # 构建提示词
        prompt = self.config.get("prompt_template", "").format(text=text)
        if not prompt:
            prompt = f"""请分析以下视频字幕文本，提取出最重要的关键词。

要求：
1. 提取5-10个最重要的关键词或短语
2. 关键词应该是名词、动词或重要的形容词
3. 优先提取出现频率高的词语
4. 返回JSON格式：[{{"word": "关键词", "importance": 0.9}}]

字幕文本：
{text}

请直接返回JSON数组，不要其他说明文字。"""

        try:
            content = self._strip_code_block(self._chat(prompt))

            keywords_data = json.loads(content)

            # 转换为 Keyword 对象
            keywords = []
            for item in keywords_data:
                keywords.append(Keyword(
                    word=item["word"],
                    importance=item.get("importance", 0.5)
                ))

            logger.info(f"关键词提取完成，共 {len(keywords)} 个关键词")
            return keywords

        except Exception as e:
            logger.error(f"关键词提取失败: {e}")
            return []

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
