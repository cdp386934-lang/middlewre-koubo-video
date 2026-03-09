"""
Pexels API服务
提供视频和图片素材搜索功能
"""
import time
from typing import Dict, List, Optional
import requests
from loguru import logger


class PexelsService:
    """Pexels API客户端"""

    def __init__(self, config: dict):
        """
        初始化Pexels服务

        Args:
            config: 配置字典,包含api_key和base_url
        """
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "https://api.pexels.com/v1")
        self.rate_limit_delay = config.get("rate_limit_delay", 0.5)

        if not self.api_key:
            logger.warning("Pexels API key未配置")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": self.api_key
        })

    def search_videos(self, query: str, per_page: int = 5, orientation: str = "landscape") -> List[Dict]:
        """
        搜索视频素材

        Args:
            query: 搜索关键词
            per_page: 每页结果数量
            orientation: 视频方向 (landscape/portrait/square)

        Returns:
            视频数据列表
        """
        if not self.api_key:
            logger.warning("Pexels API key未配置,跳过视频搜索")
            return []

        try:
            url = f"{self.base_url}/videos/search"
            params = {
                "query": query,
                "per_page": per_page,
                "orientation": orientation
            }

            time.sleep(self.rate_limit_delay)
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            videos = data.get("videos", [])
            logger.info(f"为关键词'{query}'找到{len(videos)}个视频")
            return videos

        except requests.exceptions.RequestException as e:
            logger.warning(f"搜索视频失败 (关键词: {query}): {e}")
            return []

    def search_photos(self, query: str, per_page: int = 5, orientation: str = "landscape") -> List[Dict]:
        """
        搜索图片素材

        Args:
            query: 搜索关键词
            per_page: 每页结果数量
            orientation: 图片方向 (landscape/portrait/square)

        Returns:
            图片数据列表
        """
        if not self.api_key:
            logger.warning("Pexels API key未配置,跳过图片搜索")
            return []

        try:
            url = f"{self.base_url}/search"
            params = {
                "query": query,
                "per_page": per_page,
                "orientation": orientation
            }

            time.sleep(self.rate_limit_delay)
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            photos = data.get("photos", [])
            logger.info(f"为关键词'{query}'找到{len(photos)}张图片")
            return photos

        except requests.exceptions.RequestException as e:
            logger.warning(f"搜索图片失败 (关键词: {query}): {e}")
            return []

    def get_video_file_url(self, video_data: Dict, quality: str = "hd") -> Optional[str]:
        """
        从视频数据中提取下载URL

        Args:
            video_data: Pexels视频数据
            quality: 视频质量 (hd/sd)

        Returns:
            视频下载URL,如果未找到则返回None
        """
        try:
            video_files = video_data.get("video_files", [])

            # 优先查找指定质量
            for file in video_files:
                if file.get("quality") == quality:
                    return file.get("link")

            # 如果没有找到,返回第一个可用的
            if video_files:
                return video_files[0].get("link")

            return None

        except Exception as e:
            logger.warning(f"提取视频URL失败: {e}")
            return None

    def get_photo_file_url(self, photo_data: Dict, size: str = "large") -> Optional[str]:
        """
        从图片数据中提取下载URL

        Args:
            photo_data: Pexels图片数据
            size: 图片尺寸 (original/large/medium/small)

        Returns:
            图片下载URL,如果未找到则返回None
        """
        try:
            src = photo_data.get("src", {})
            return src.get(size) or src.get("original")

        except Exception as e:
            logger.warning(f"提取图片URL失败: {e}")
            return None
