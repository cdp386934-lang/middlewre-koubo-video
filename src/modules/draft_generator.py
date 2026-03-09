from pathlib import Path
from typing import Dict, List, Optional, Union
from loguru import logger
from ..services.capcut_service import CapCutService
from ..models.subtitle import SubtitleData
from ..models.keyword import KeywordData
from ..models.material import MaterialData
from ..models.draft import DraftMetadata
from ..utils.file_handler import write_json
from ..utils.file_server import LocalFileServer


class DraftGenerator:
    """剪映草稿生成模块"""

    def __init__(self, config: dict):
        self.config = config

        project_root = Path(config["paths"]["input"]).parent
        self.file_server = LocalFileServer(directory=str(project_root), port=8000)
        self.file_server.start()

        self.capcut_service = CapCutService(config, file_server=self.file_server)

    def generate(self, video_path: Union[str, Path], subtitle_data: SubtitleData,
                keyword_data: KeywordData, video_info: Dict,
                bgm_path: Optional[Union[str, Path]] = None,
                bgm_segments: Optional[List] = None,
                bgm_data=None,
                material_data: Optional[MaterialData] = None,
                generated_title: Optional[str] = None) -> DraftMetadata:
        """
        生成剪映草稿

        Args:
            video_path: 视频文件路径
            subtitle_data: 字幕数据
            keyword_data: 关键词数据
            video_info: 视频信息
            bgm_path: 背景音乐路径（可选，向后兼容）
            bgm_segments: BGM片段列表（可选，新参数）
            bgm_data: BGM配置数据（可选，新参数）
            material_data: 素材数据（可选）

        Returns:
            DraftMetadata: 草稿元数据
        """
        video_path = Path(video_path)
        draft_name = video_path.stem

        logger.info(f"开始生成剪映草稿: {draft_name}")

        draft_id = self.capcut_service.create_draft(
            width=video_info['width'],
            height=video_info['height']
        )

        timeline_entries = self._build_timeline_entries(subtitle_data)
        video_segments = self._prepare_video_segments(timeline_entries)

        if video_segments:
            self.capcut_service.add_video_segments(str(video_path.absolute()), video_segments)
            logger.info(f"已添加 {len(video_segments)} 个视频片段")
        else:
            logger.warning("没有片段数据，使用原始方式添加整个视频")
            self.capcut_service.add_videos([str(video_path.absolute())])

        has_bgm = False
        if bgm_segments and bgm_data:
            project_root = Path(self.config["paths"]["input"]).parent
            self.capcut_service.add_bgm_segments(bgm_segments, bgm_data, project_root)
            has_bgm = True
            logger.info(f"已添加 {len(bgm_segments)} 个背景音乐片段")
        elif bgm_path and Path(bgm_path).exists():
            self.capcut_service.add_audios([str(Path(bgm_path).absolute())], volume=0.3)
            has_bgm = True
            logger.info("已添加背景音乐（兼容模式）")

        captions = self._prepare_captions(timeline_entries)
        if captions:
            self.capcut_service.add_captions(captions)
            logger.info(f"已添加 {len(captions)} 条字幕")

        overlay_texts = self._build_overlay_texts(
            duration=timeline_entries[-1]["target_end"] if timeline_entries else video_info["duration"],
            generated_title=generated_title,
        )
        self._add_overlay_texts(overlay_texts)

        if material_data:
            self._add_materials_to_draft(draft_id, material_data, timeline_entries)

        draft_path = self.capcut_service.save_draft()

        draft_metadata = DraftMetadata(
            draft_id=draft_id,
            draft_name=draft_name,
            draft_path=draft_path,
            video_path=str(video_path.absolute()),
            duration=video_info['duration'],
            resolution=video_info['resolution'],
            fps=video_info['fps'],
            has_subtitles=len(captions) > 0,
            has_bgm=has_bgm,
            keyword_count=len(keyword_data.keywords),
            generated_title=generated_title,
            author_name=self.config.get("overlay_text", {}).get("author", {}).get("name") or None,
            author_identity=self.config.get("overlay_text", {}).get("author", {}).get("identity") or None,
        )

        metadata_path = Path(self.config["paths"]["drafts"]) / f"{draft_name}_metadata.json"
        write_json(draft_metadata.model_dump(), metadata_path)
        logger.info(f"草稿元数据已保存: {metadata_path}")

        return draft_metadata

    def _build_overlay_texts(self, duration: float, generated_title: Optional[str]) -> List[Dict]:
        """构建标题、作者、身份等静态文案轨道。"""
        overlay_config = self.config.get("overlay_text", {})
        items: List[Dict] = []

        title_config = overlay_config.get("title", {})
        if title_config.get("enabled", True) and generated_title:
            title_start = float(title_config.get("start", 0.0))
            title_duration = min(float(title_config.get("duration", 4.0)), max(duration - title_start, 0.0))
            if title_duration > 0:
                items.append({
                    "name": "title",
                    "captions": [{
                        "start": int(title_start * 1_000_000),
                        "end": int((title_start + title_duration) * 1_000_000),
                        "text": generated_title,
                        "font_size": int(title_config.get("font_size", 34)),
                    }],
                    "options": self._build_caption_options(title_config),
                })

        author_config = overlay_config.get("author", {})
        if author_config.get("enabled", False):
            author_start = float(author_config.get("start", 0.5))
            author_duration = min(float(author_config.get("duration", 4.0)), max(duration - author_start, 0.0))
            if author_duration > 0:
                author_name = str(author_config.get("name", "")).strip()
                author_identity = str(author_config.get("identity", "")).strip()

                if author_name:
                    items.append({
                        "name": "author_name",
                        "captions": [{
                            "start": int(author_start * 1_000_000),
                            "end": int((author_start + author_duration) * 1_000_000),
                            "text": author_name,
                            "font_size": int(author_config.get("name_font_size", 22)),
                        }],
                        "options": self._build_caption_options(author_config, prefix="name_"),
                    })

                if author_identity:
                    items.append({
                        "name": "author_identity",
                        "captions": [{
                            "start": int(author_start * 1_000_000),
                            "end": int((author_start + author_duration) * 1_000_000),
                            "text": author_identity,
                            "font_size": int(author_config.get("identity_font_size", 18)),
                        }],
                        "options": self._build_caption_options(author_config, prefix="identity_"),
                    })

        return items

    def _build_caption_options(self, config: Dict, prefix: str = "") -> Dict:
        """将 overlay 配置转换为 capcut-mate add_captions 参数。"""
        def pick(key: str, default=None):
            return config.get(f"{prefix}{key}", config.get(key, default))

        return {
            "text_color": pick("text_color", "#FFFFFF"),
            "alignment": int(pick("alignment", 1)),
            "font_size": int(pick("font_size", 18)),
            "transform_x": float(pick("transform_x", 0.0)),
            "transform_y": float(pick("transform_y", -300.0)),
            "scale_x": float(pick("scale_x", 1.0)),
            "scale_y": float(pick("scale_y", 1.0)),
            "has_shadow": bool(pick("has_shadow", True)),
        }

    def _add_overlay_texts(self, overlay_texts: List[Dict]) -> None:
        for overlay in overlay_texts:
            self.capcut_service.add_captions(overlay["captions"], options=overlay["options"])
            logger.info(f"已添加文案轨道: {overlay['name']}")

    def _build_timeline_entries(self, subtitle_data: SubtitleData) -> List[Dict]:
        """将原始字幕时间轴压缩成剪映目标时间轴。"""
        entries: List[Dict] = []
        target_time = 0.0

        for seg in subtitle_data.segments:
            if seg.removed == 1:
                logger.debug(f"跳过被移除的片段: {seg.start:.2f}s - {seg.end:.2f}s")
                continue

            duration = seg.end - seg.start
            if duration <= 0:
                logger.warning(f"跳过无效片段: id={seg.id}, start={seg.start}, end={seg.end}")
                continue

            entries.append({
                "segment_id": seg.id,
                "text": seg.text,
                "keyword": seg.keyword,
                "keywords": list(seg.keywords),
                "text_grade": seg.text_grade,
                "video_grade": seg.video_grade,
                "source_start": seg.start,
                "source_end": seg.end,
                "target_start": target_time,
                "target_end": target_time + duration,
            })
            target_time += duration

        logger.info(f"构建了 {len(entries)} 条时间轴条目，压缩后总时长: {target_time:.2f}秒")
        return entries

    def _prepare_video_segments(self, timeline_entries: List[Dict]) -> List[Dict]:
        """
        根据压缩后的时间轴准备视频片段。

        这里的关键点是：
        - `source_start/source_end` 表示原视频中的截取范围
        - `target_start` 表示截取后的片段在新时间轴上的开始时间
        """
        if not timeline_entries:
            return []

        merge_tolerance = float(self.config.get("breath_removal", {}).get("merge_tolerance", 1e-6))
        merged_segments: List[Dict] = []

        for entry in timeline_entries:
            if not merged_segments:
                merged_segments.append({
                    "source_start": entry["source_start"],
                    "source_end": entry["source_end"],
                    "target_start": entry["target_start"],
                    "target_end": entry["target_end"],
                    "video_grade": entry.get("video_grade", 1),
                })
                continue

            last = merged_segments[-1]
            source_gap = entry["source_start"] - last["source_end"]
            target_gap = entry["target_start"] - last["target_end"]
            can_merge = (
                abs(source_gap) <= merge_tolerance
                and abs(target_gap) <= 1e-6
                and last.get("video_grade", 1) == 1
                and entry.get("video_grade", 1) == 1
            )
            if can_merge:
                last["source_end"] = entry["source_end"]
                last["target_end"] = entry["target_end"]
            else:
                merged_segments.append({
                    "source_start": entry["source_start"],
                    "source_end": entry["source_end"],
                    "target_start": entry["target_start"],
                    "target_end": entry["target_end"],
                    "video_grade": entry.get("video_grade", 1),
                })

        result = []
        for segment in merged_segments:
            result.append({
                "source_start": segment["source_start"],
                "source_end": segment["source_end"],
                "target_start": segment["target_start"],
            })

        total_duration = merged_segments[-1]["target_end"] if merged_segments else 0.0
        logger.info(
            f"准备了 {len(result)} 个视频片段（原始字幕条目 {len(timeline_entries)} 条），总时长: {total_duration:.2f}秒"
        )
        return result

    def _prepare_captions(self, timeline_entries: List[Dict]) -> List[Dict]:
        """将字幕映射到压缩后的目标时间轴。"""
        subtitle_config = self.config.get("subtitle", {})
        font_size = int(subtitle_config.get("font_size", 24))
        keyword_color = subtitle_config.get("keyword_color", "#FFD700")
        keyword_font_size = int(subtitle_config.get("keyword_font_size", font_size))

        captions: List[Dict] = []
        for entry in timeline_entries:
            caption = {
                "start": int(entry["target_start"] * 1_000_000),
                "end": int(entry["target_end"] * 1_000_000),
                "text": entry["text"],
                "font_size": font_size,
            }

            if entry.get("keyword"):
                caption["keyword"] = entry["keyword"]
                caption["keyword_color"] = keyword_color
                caption["keyword_font_size"] = keyword_font_size

            captions.append(caption)

        return captions

    def _add_materials_to_draft(
        self,
        draft_id: str,
        material_data: MaterialData,
        timeline_entries: List[Dict]
    ) -> None:
        """将素材按压缩后的目标时间轴添加到草稿。"""
        logger.info(f"开始添加{len(material_data.materials)}个素材到草稿")

        timeline_map = {entry["segment_id"]: entry for entry in timeline_entries}
        added_count = 0

        for material in material_data.materials:
            if material.segment_id is None:
                logger.warning(f"素材{material.id}没有关联的segment,跳过")
                continue

            entry = timeline_map.get(material.segment_id)
            if not entry:
                logger.warning(f"未找到segment {material.segment_id} 的压缩时间轴信息,跳过素材{material.id}")
                continue

            start_time = entry["target_start"]
            duration = entry["target_end"] - entry["target_start"]

            try:
                if material.type == "video":
                    result = self.capcut_service.add_video_material(
                        draft_id,
                        material.download_url,
                        start_time,
                        duration
                    )
                elif material.type == "photo":
                    result = self.capcut_service.add_image_material(
                        draft_id,
                        material.download_url,
                        start_time,
                        duration
                    )
                else:
                    logger.warning(f"未知素材类型: {material.type}")
                    continue

                if result.get("code") == 0:
                    added_count += 1
                    logger.debug(f"成功添加素材: {material.keyword} ({material.type})")

            except Exception as e:
                logger.error(f"添加素材失败 ({material.keyword}): {e}")
                continue

        logger.info(f"素材添加完成,成功添加{added_count}/{len(material_data.materials)}个素材")
