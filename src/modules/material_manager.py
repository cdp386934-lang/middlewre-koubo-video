import json
import os
import time
from pathlib import Path
from typing import List, Optional

import requests
from loguru import logger


class MaterialManager:
    """素材管理模块"""

    def __init__(self, config: dict):
        self.config = config
        pexels_config = config.get("pexels", {})

        api_key = self._resolve_env_value(pexels_config.get("api_key"))
        config_enabled = bool(pexels_config.get("enabled", True))
        # 仅当开关开启且 API key 可用时，素材功能才真正启用
        self.enabled = config_enabled and bool(api_key)

        if self.enabled:
            from src.services.pexels_service import PexelsService
            from src.services.deepseek_service import DeepSeekService

            runtime_pexels_config = dict(pexels_config)
            runtime_pexels_config["api_key"] = api_key
            self.pexels_service = PexelsService(runtime_pexels_config)
            self.deepseek_service = DeepSeekService(config)
            self.material_dir = Path(config["paths"].get("materials", "output/materials"))
            self.material_dir.mkdir(parents=True, exist_ok=True)
            self.download_dir = self.material_dir / "downloads"
            self.download_dir.mkdir(parents=True, exist_ok=True)

            # 配置参数
            # 不再通过配置限制关键词数量和 query 数量，按实际上下文全量处理。
            # per_page 仅控制单次 Pexels API 返回量，不影响插入点策略。
            self.search_per_page = int(pexels_config.get("search_per_page", 5))
            self.orientation = pexels_config.get("orientation", "landscape")
            self.video_quality = pexels_config.get("video_quality", "hd")
            self.photo_size = pexels_config.get("photo_size", "large")
            self.include_photos = bool(pexels_config.get("include_photos", False))
            self.min_duration = int(pexels_config.get("min_duration", 3))
            self.max_duration = int(pexels_config.get("max_duration", 8))
            self.locale = pexels_config.get("locale", "en-US")
            self.download_timeout = int(pexels_config.get("download_timeout", 30))
            self.download_retries = int(pexels_config.get("download_retries", 2))
            self.shot_preferences = [str(v).lower() for v in pexels_config.get("shot_preferences", [])]
        else:
            if not config_enabled:
                logger.info("pexels.enabled=false，素材管理功能已禁用")
            else:
                logger.warning("Pexels API key未配置或为空，素材管理功能已禁用")

    @staticmethod
    def _resolve_env_value(value: Optional[str]) -> Optional[str]:
        raw = str(value or "").strip()
        if not raw:
            return None
        if raw.startswith("${") and raw.endswith("}"):
            env_var = raw[2:-1].strip()
            return os.getenv(env_var)
        return raw

    def manage(self, subtitle_data=None, keyword_data=None):
        """
        管理素材获取流程

        Args:
            subtitle_data: 字幕数据
            keyword_data: 关键词数据

        Returns:
            MaterialData: 素材数据（如果启用）或 None
        """
        if not self.enabled:
            logger.info("素材管理（未启用）")
            return None

        from src.models.material import MaterialData

        logger.info("开始素材管理")

        # 1. 提取关键词（不做数量上限裁剪）
        top_keywords = self._get_top_keywords(keyword_data)
        logger.info(f"将基于{len(top_keywords)}个关键词进行素材搜索")

        # 2. 为每个关键词搜索素材
        all_materials = []
        for keyword_obj in top_keywords:
            keyword = keyword_obj.word
            logger.info(f"搜索关键词: \"{keyword}\"")
            context = self._build_keyword_context(keyword_obj, subtitle_data)
            queries = self.deepseek_service.generate_broll_queries(keyword, context)
            if not queries:
                queries = [keyword]

            materials = self._search_materials_for_keyword(keyword, queries)

            # 3. 映射素材到字幕segments
            for material in materials:
                self._map_material_to_segments(material, keyword, keyword_data, subtitle_data)

            all_materials.extend(materials)

        material_data = MaterialData(materials=all_materials)

        # 4. 保存元数据
        metadata_path = self.material_dir / "metadata.json"
        self._save_metadata(material_data, metadata_path)

        logger.info(f"素材管理完成,共获取{len(all_materials)}个素材")
        return material_data

    def _get_top_keywords(self, keyword_data, n=None):
        """提取关键词；默认不限制数量，仅按重要性排序。"""
        sorted_keywords = sorted(
            keyword_data.keywords,
            key=lambda k: k.importance,
            reverse=True
        )
        if n is None:
            return sorted_keywords
        return sorted_keywords[:n]

    def _search_materials_for_keyword(self, keyword: str, queries: List[str]):
        """为单个关键词搜索素材（最多返回1个）。"""
        from src.models.material import Material

        seen_ids = set()
        selected_material = None

        for query in queries:
            videos = self.pexels_service.search_videos(
                query,
                per_page=self.search_per_page,
                orientation=self.orientation,
                min_duration=self.min_duration,
                max_duration=self.max_duration,
                locale=self.locale,
            )
            videos = self._filter_videos(videos)

            for video in videos:
                if video["id"] in seen_ids:
                    continue
                download_url = self.pexels_service.get_video_file_url(video, self.video_quality)
                if not download_url:
                    continue
                local_path = self._download_material(download_url, f"{video['id']}.mp4")

                material = Material(
                    id=video["id"],
                    type="video",
                    keyword=keyword,
                    source_query=query,
                    url=video["url"],
                    download_url=download_url,
                    local_path=str(local_path) if local_path else None,
                    width=video["width"],
                    height=video["height"],
                    duration=video.get("duration"),
                    photographer=video["user"]["name"],
                    photographer_url=video["user"]["url"]
                )
                selected_material = material
                seen_ids.add(video["id"])
                break

            if selected_material:
                break

            # 搜索图片（默认关闭）
            if not self.include_photos:
                continue

            photos = self.pexels_service.search_photos(
                query,
                per_page=self.search_per_page,
                orientation=self.orientation
            )

            for photo in photos:
                if photo["id"] in seen_ids:
                    continue
                download_url = self.pexels_service.get_photo_file_url(photo, self.photo_size)
                if not download_url:
                    continue
                local_path = self._download_material(download_url, f"{photo['id']}.jpg")

                material = Material(
                    id=photo["id"],
                    type="photo",
                    keyword=keyword,
                    source_query=query,
                    url=photo["url"],
                    download_url=download_url,
                    local_path=str(local_path) if local_path else None,
                    width=photo["width"],
                    height=photo["height"],
                    photographer=photo["photographer"],
                    photographer_url=photo["photographer_url"]
                )
                selected_material = material
                seen_ids.add(photo["id"])
                break

            if selected_material:
                break

        if selected_material:
            logger.info(f"关键词 \"{keyword}\" 已选择1个素材: {selected_material.type} ({selected_material.id})")
            return [selected_material]
        logger.warning(f"关键词 \"{keyword}\" 未检索到可用素材")
        return []

    def _filter_videos(self, videos: List[dict]) -> List[dict]:
        """按时长硬筛选，并对镜头偏好做轻量排序。"""
        candidates = []
        for video in videos:
            duration = float(video.get("duration") or 0.0)
            if duration <= 0:
                continue
            if duration < self.min_duration or duration > self.max_duration:
                continue

            score = 0
            score += 2 if self.orientation == "landscape" and video.get("width", 0) >= video.get("height", 0) else 0
            score += 2 if 3 <= duration <= 8 else 0
            page_url = str(video.get("url", "")).lower()
            for token in self.shot_preferences:
                if token in page_url:
                    score += 1
            candidates.append((score, video))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [video for _, video in candidates]

    def _build_keyword_context(self, keyword_obj, subtitle_data) -> str:
        """从关键词命中的首个字幕段提取上下文。"""
        if not subtitle_data or not getattr(subtitle_data, "segments", None):
            return keyword_obj.word

        segment_map = {seg.id: seg for seg in subtitle_data.segments}
        if not keyword_obj.positions:
            return keyword_obj.word
        segment = segment_map.get(keyword_obj.positions[0])
        if not segment:
            return keyword_obj.word
        return str(getattr(segment, "text", "")).strip() or keyword_obj.word

    def _download_material(self, url: str, filename: str) -> Optional[Path]:
        """下载素材到本地缓存，失败时返回 None。"""
        target = self.download_dir / filename
        if target.exists():
            return target

        for attempt in range(1, self.download_retries + 2):
            try:
                with requests.get(url, timeout=self.download_timeout, stream=True) as response:
                    response.raise_for_status()
                    with open(target, "wb") as file_obj:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                file_obj.write(chunk)
                return target
            except Exception as exc:
                logger.warning(f"下载素材失败({attempt}): {url} -> {exc}")
                if attempt <= self.download_retries:
                    time.sleep(0.3)
        return None

    def _map_material_to_segments(self, material, keyword, keyword_data, subtitle_data):
        """将素材映射到对应的字幕segments"""
        # 找到包含该关键词的所有segments
        matching_segments = []
        for kw in keyword_data.keywords:
            if kw.word == keyword:
                matching_segments = kw.positions
                break

        # 将素材映射到第一个匹配的segment
        if matching_segments:
            material.segment_id = matching_segments[0]

    def _save_metadata(self, material_data, output_path):
        """保存素材元数据到JSON文件"""
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(material_data.model_dump(), f, ensure_ascii=False, indent=2)
            logger.info(f"素材元数据已保存到: {output_path}")
        except Exception as e:
            logger.error(f"保存素材元数据失败: {e}")
