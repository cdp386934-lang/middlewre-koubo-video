import json
import os
import subprocess
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

        project_root = self._get_project_root()
        self.file_server = LocalFileServer(directory=str(project_root), port=8000)
        self.file_server.start()

        self.capcut_service = CapCutService(config, file_server=self.file_server)

    def _get_project_root(self) -> Path:
        return Path(self.config["paths"]["input"]).parent

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

        timeline_entries = self._build_timeline_entries(subtitle_data)
        draft_duration = self._get_target_draft_duration(subtitle_data, video_info)
        draft_layout = self._get_draft_layout_config()
        main_video_layout = self._calculate_main_video_layout(video_info, draft_layout)
        capcut_video_path = self._ensure_capcut_compatible_video(video_path)

        draft_id = self.capcut_service.create_draft(
            width=draft_layout.get("width", video_info['width']),
            height=draft_layout.get("height", video_info['height'])
        )

        background_path = self._ensure_background_image(
            draft_name=draft_name,
            draft_layout=draft_layout,
            video_layout=main_video_layout,
        )
        if background_path:
            self.capcut_service.add_background_image(
                image_path=background_path,
                width=int(draft_layout.get("width", video_info['width'])),
                height=int(draft_layout.get("height", video_info['height'])),
                duration=draft_duration,
            )
            logger.info(f"已添加灰白色封面背景图: {background_path.name}")

        has_removed_segments = self._has_removed_segments(subtitle_data)

        if has_removed_segments:
            video_segments = self._prepare_video_segments(timeline_entries)
            if video_segments:
                self.capcut_service.add_video_segments(str(capcut_video_path.absolute()), video_segments)
                logger.info(f"已添加 {len(video_segments)} 个视频片段")
            else:
                logger.warning("没有有效切口片段，回退为添加完整主视频")
                self.capcut_service.add_videos([str(capcut_video_path.absolute())])
        else:
            self.capcut_service.add_videos([str(capcut_video_path.absolute())])
            logger.info("未检测到去气口切口，直接添加完整主视频")

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
            subtitle_options = self._build_subtitle_options(draft_layout, main_video_layout)
            self.capcut_service.add_captions(captions, options=subtitle_options)
            logger.info(f"已添加 {len(captions)} 条字幕")

        overlay_texts = self._build_overlay_texts(
            duration=draft_duration,
            generated_title=generated_title,
            video_layout=main_video_layout,
        )
        self._add_overlay_texts(overlay_texts)

        if material_data:
            self._add_materials_to_draft(draft_id, material_data, timeline_entries)

        draft_path = self.capcut_service.save_draft()
        self._postprocess_main_timeline_and_background(draft_duration)
        self._apply_main_video_layout_to_local_draft(video_info, draft_layout)
        self._fix_draft_file_paths()

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

    @staticmethod
    def _get_target_draft_duration(subtitle_data: SubtitleData, video_info: Dict) -> float:
        """计算最终草稿时长：原视频总时长减去被移除的片段时长。"""
        removed_duration = sum(
            max(segment.end - segment.start, 0.0)
            for segment in subtitle_data.segments
            if segment.removed == 1
        )
        return max(float(video_info.get("duration") or 0.0) - removed_duration, 0.0)

    def _get_draft_layout_config(self) -> Dict:
        """获取微播封面布局配置。"""
        layout_config = self.config.get("draft_layout", {})
        if not layout_config.get("enabled", False):
            return {"enabled": False}

        main_video_config = layout_config.get("main_video", {})
        return {
            "enabled": True,
            "width": int(layout_config.get("width", 1080)),
            "height": int(layout_config.get("height", 1920)),
            "background_color": layout_config.get("background_color", "#F2F1EC"),
            "main_video": {
                "max_width": float(main_video_config.get("max_width", 960)),
                "max_height": float(main_video_config.get("max_height", 980)),
                "transform_x": float(main_video_config.get("transform_x", 0.0)),
                "transform_y": float(main_video_config.get("transform_y", 0.0)),
            },
        }

    def _get_temp_dir(self) -> Path:
        """获取项目内可复用的临时目录。"""
        temp_path = Path(self.config["paths"].get("temp", "temp"))
        if not temp_path.is_absolute():
            temp_path = self._get_project_root() / temp_path
        temp_path.mkdir(parents=True, exist_ok=True)
        return temp_path

    def _ensure_background_image(self, draft_name: str, draft_layout: Dict, video_layout: Optional[Dict] = None) -> Optional[Path]:
        """生成 9:16 背景图；若有视频布局则中间挖空避免遮挡主视频。"""
        if not draft_layout.get("enabled"):
            return None

        background_path = self._get_temp_dir() / f"{draft_name}_cover_background.png"
        width = int(draft_layout["width"])
        height = int(draft_layout["height"])
        color_hex = draft_layout["background_color"].replace("#", "")
        color_value = f"0x{color_hex}"

        if video_layout:
            display_height = float(video_layout.get("display_height") or 0.0)
            transform_y = float(video_layout.get("transform_y") or 0.0)
            center_y = (height / 2.0) + transform_y
            video_top = max(int(round(center_y - display_height / 2.0)), 0)
            video_bottom = min(int(round(center_y + display_height / 2.0)), height)

            top_h = max(video_top, 0)
            bottom_h = max(height - video_bottom, 0)
            filters = [f"color=c=black@0.0:s={width}x{height}", "format=rgba"]
            if top_h > 0:
                filters.append(
                    f"drawbox=x=0:y=0:w=iw:h={top_h}:color={color_value}@1:t=fill:replace=1"
                )
            if bottom_h > 0:
                filters.append(
                    f"drawbox=x=0:y={video_bottom}:w=iw:h={bottom_h}:color={color_value}@1:t=fill:replace=1"
                )
            filter_chain = ",".join(filters)
            command = [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                filter_chain,
                "-frames:v",
                "1",
                "-pix_fmt",
                "rgba",
                str(background_path),
            ]
        else:
            command = [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color_value}:s={width}x{height}",
                "-frames:v",
                "1",
                str(background_path),
            ]

        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            return background_path
        except FileNotFoundError:
            logger.warning("未找到 ffmpeg，跳过灰白色背景图生成")
        except subprocess.CalledProcessError as exc:
            logger.warning(f"生成灰白色背景图失败，跳过背景图轨道: {exc.stderr.strip()}")
        return None

    @staticmethod
    def _probe_media(media_path: Path) -> Optional[Dict]:
        """读取媒体编码信息。"""
        try:
            import ffmpeg
            return ffmpeg.probe(str(media_path))
        except Exception as exc:
            logger.warning(f"探测媒体信息失败，回退原视频: {media_path} ({exc})")
            return None

    @staticmethod
    def _needs_capcut_video_normalization(probe: Optional[Dict]) -> bool:
        """判断是否需要转成更稳定的 H.264/AAC 格式。"""
        if not probe:
            return False

        streams = probe.get("streams", [])
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
        if not video_stream:
            return False

        video_ok = (
            video_stream.get("codec_name") == "h264"
            and video_stream.get("pix_fmt") == "yuv420p"
        )
        if not audio_stream:
            return True

        audio_ok = (
            audio_stream.get("codec_name") == "aac"
            and audio_stream.get("sample_rate") in {"44100", "48000"}
            and int(audio_stream.get("channels") or 0) in {1, 2}
        )
        return not (video_ok and audio_ok)

    def _ensure_capcut_compatible_video(self, video_path: Union[str, Path]) -> Path:
        """将主视频规范化为剪映更稳定识别的 MP4(H.264 + AAC 48k)。"""
        video_path = Path(video_path)
        probe = self._probe_media(video_path)
        if not self._needs_capcut_video_normalization(probe):
            return video_path

        output_path = self._get_temp_dir() / f"{video_path.stem}_capcut_ready.mp4"
        if output_path.exists() and output_path.stat().st_mtime >= video_path.stat().st_mtime:
            return output_path

        streams = probe.get("streams", []) if probe else []
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)

        command = ["ffmpeg", "-y", "-i", str(video_path)]
        if audio_stream is None:
            command.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"])

        command.extend(["-map", "0:v:0"])
        if audio_stream is None:
            command.extend(["-map", "1:a:0", "-shortest"])
        else:
            command.extend(["-map", "0:a:0"])

        if video_stream and video_stream.get("codec_name") == "h264" and video_stream.get("pix_fmt") == "yuv420p":
            command.extend(["-c:v", "copy"])
        else:
            command.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18"])

        command.extend([
            "-c:a", "aac",
            "-profile:a", "aac_low",
            "-ar", "48000",
            "-ac", "2",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_path),
        ])

        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            logger.info(f"已生成剪映兼容视频: {output_path.name}")
            return output_path
        except FileNotFoundError:
            logger.warning("未找到 ffmpeg，无法生成剪映兼容视频，回退原视频")
        except subprocess.CalledProcessError as exc:
            logger.warning(f"视频转码失败，回退原视频: {exc.stderr.strip()}")
        return video_path

    def _ensure_capcut_compatible_broll_video(self, video_path: Union[str, Path]) -> Path:
        """将 B-roll 视频规范化为剪映可稳定导入格式。"""
        video_path = Path(video_path)
        if not video_path.exists():
            return video_path

        output_path = self._get_temp_dir() / f"{video_path.stem}_broll_ready.mp4"
        if output_path.exists() and output_path.stat().st_mtime >= video_path.stat().st_mtime:
            return output_path

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            return output_path
        except Exception as exc:
            logger.warning(f"B-roll 视频转码失败，回退原文件: {video_path} ({exc})")
            return video_path

    def _calculate_main_video_layout(self, video_info: Dict, draft_layout: Dict) -> Dict:
        """计算主视频在 9:16 封面中的实际展示区域。"""
        canvas_width = float(draft_layout.get("width", video_info.get("width") or 1080))
        canvas_height = float(draft_layout.get("height", video_info.get("height") or 1920))
        main_video_config = draft_layout.get("main_video", {})
        scale = self._calculate_main_video_scale(
            video_info,
            max_width=float(main_video_config.get("max_width", video_info.get("width") or canvas_width)),
            max_height=float(main_video_config.get("max_height", video_info.get("height") or canvas_height)),
        )
        transform_x = float(main_video_config.get("transform_x", 0.0))
        transform_y = float(main_video_config.get("transform_y", 0.0))
        display_width = float(video_info.get("width") or 0.0) * scale
        display_height = float(video_info.get("height") or 0.0) * scale

        return {
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
            "scale": scale,
            "transform_x": transform_x,
            "transform_y": transform_y,
            "display_width": display_width,
            "display_height": display_height,
            "top": transform_y - (display_height / 2),
            "bottom": transform_y + (display_height / 2),
        }

    def _build_subtitle_options(self, draft_layout: Dict, video_layout: Dict) -> Optional[Dict]:
        """为正文字幕构建样式和定位参数。"""
        subtitle_config = self.config.get("subtitle", {})
        transform_y = float(subtitle_config.get("transform_y", 780.0))
        if draft_layout.get("enabled") and subtitle_config.get("anchor_to_video", True):
            margin_to_video = float(subtitle_config.get("margin_to_video", 72.0))
            transform_y = video_layout["bottom"] + margin_to_video + (int(subtitle_config.get("font_size", 24)) / 2)

        return {
            "text_color": subtitle_config.get("font_color", "#333333"),
            "alignment": int(subtitle_config.get("alignment", 1)),
            "font_size": int(subtitle_config.get("font_size", 24)),
            "transform_x": float(subtitle_config.get("transform_x", 0.0)),
            "transform_y": transform_y,
            "scale_x": float(subtitle_config.get("scale_x", 1.0)),
            "scale_y": float(subtitle_config.get("scale_y", 1.0)),
            "has_shadow": bool(subtitle_config.get("has_shadow", False)),
        }

    @staticmethod
    def _calculate_main_video_scale(video_info: Dict, max_width: float, max_height: float) -> float:
        """根据目标展示区域计算主视频缩放比例。"""
        width = float(video_info.get("width") or 0)
        height = float(video_info.get("height") or 0)
        if width <= 0 or height <= 0:
            return 1.0

        return min(max_width / width, max_height / height, 1.0)

    @staticmethod
    def _apply_video_layout_to_draft_content(
        draft_content: Dict,
        scale: float,
        transform_x: float,
        transform_y: float,
    ) -> bool:
        """将主视频缩放并居中到微播封面布局。"""
        video_tracks = [
            track for track in draft_content.get("tracks", [])
            if track.get("type") == "video" and track.get("segments")
        ]
        if not video_tracks:
            return False

        named_main_tracks = [track for track in video_tracks if track.get("name") == "main_track"]
        main_track = named_main_tracks[0] if named_main_tracks else (video_tracks[1] if len(video_tracks) > 1 else video_tracks[0])
        for segment in main_track.get("segments", []):
            clip = segment.setdefault("clip", {})
            clip_scale = clip.setdefault("scale", {})
            clip_scale["x"] = scale
            clip_scale["y"] = scale

            clip_transform = clip.setdefault("transform", {})
            clip_transform["x"] = transform_x
            clip_transform["y"] = transform_y

            uniform_scale = segment.setdefault("uniform_scale", {})
            uniform_scale["on"] = True
            uniform_scale["value"] = scale

        return True

    def _apply_main_video_layout_to_local_draft(self, video_info: Dict, draft_layout: Dict) -> None:
        """保存草稿后，对本地 draft_content.json 再次修正主视频布局。"""
        if not draft_layout.get("enabled"):
            return

        get_local_draft_dir = getattr(self.capcut_service, "get_local_draft_dir", None)
        if not callable(get_local_draft_dir):
            return

        local_draft_dir = get_local_draft_dir()
        if not local_draft_dir:
            logger.warning("未找到本地剪映草稿目录，跳过主视频布局修正")
            return

        content_path = Path(local_draft_dir) / "draft_content.json"
        if not content_path.exists():
            logger.warning(f"未找到草稿内容文件，跳过主视频布局修正: {content_path}")
            return

        with open(content_path, "r", encoding="utf-8") as file_obj:
            draft_content = json.load(file_obj)

        main_video_layout = self._calculate_main_video_layout(video_info, draft_layout)
        transform_x = main_video_layout["transform_x"] / max(float(draft_layout["width"]), 1.0)
        transform_y = main_video_layout["transform_y"] / max(float(draft_layout["height"]), 1.0)

        changed = self._apply_video_layout_to_draft_content(
            draft_content=draft_content,
            scale=main_video_layout["scale"],
            transform_x=transform_x,
            transform_y=transform_y,
        )
        if not changed:
            logger.warning("草稿中未找到可调整的主视频轨道")
            return

        with open(content_path, "w", encoding="utf-8") as file_obj:
            json.dump(draft_content, file_obj, ensure_ascii=False, indent=2)

        os.utime(content_path, None)
        os.utime(local_draft_dir, None)
        logger.info(f"已按微播封面样式修正主视频布局: {content_path}")

    def _fix_draft_file_paths(self) -> None:
        """修复草稿文件中的文件路径，将 capcut-mate 输出路径转换为本地草稿路径"""
        get_local_draft_dir = getattr(self.capcut_service, "get_local_draft_dir", None)
        if not callable(get_local_draft_dir):
            return

        local_draft_dir = get_local_draft_dir()
        if not local_draft_dir:
            return

        # 修复 draft_content.json
        content_path = Path(local_draft_dir) / "draft_content.json"
        if content_path.exists():
            with open(content_path, "r", encoding="utf-8") as file_obj:
                draft_content = json.load(file_obj)

            fixed_count = 0
            assets_root = Path(local_draft_dir) / "assets"

            def _normalize_path(material: Dict, subfolder: str) -> bool:
                old_path = str(material.get("path", "")).strip()
                filename = os.path.basename(old_path)
                if not filename:
                    return False
                new_path = assets_root / subfolder / filename
                if new_path.exists() and str(new_path) != old_path:
                    material["path"] = str(new_path)
                    return True
                return False

            # 修复视频路径
            videos = draft_content.get('materials', {}).get('videos', [])
            for video in videos:
                # capcut-mate 可能把背景图(photo)也放在 materials.videos 下
                subfolder = "images" if str(video.get("type", "")).lower() == "photo" else "videos"
                if _normalize_path(video, subfolder):
                    fixed_count += 1
                    logger.debug(f"修复视频路径: {video.get('path')}")

            # 修复音频路径
            audios = draft_content.get('materials', {}).get('audios', [])
            for audio in audios:
                if _normalize_path(audio, "audios"):
                    fixed_count += 1
                    logger.debug(f"修复音频路径: {audio.get('path')}")

            # 修复图片路径
            images = draft_content.get('materials', {}).get('images', [])
            for image in images:
                if _normalize_path(image, "images"):
                    fixed_count += 1
                    logger.debug(f"修复图片路径: {image.get('path')}")

            if fixed_count > 0:
                with open(content_path, "w", encoding="utf-8") as file_obj:
                    json.dump(draft_content, file_obj, ensure_ascii=False, indent=2)
                logger.info(f"已修复 draft_content.json 中的 {fixed_count} 个文件路径")

        # 修复 draft_info.json
        info_path = Path(local_draft_dir) / "draft_info.json"
        if info_path.exists():
            try:
                with open(info_path, "r", encoding="utf-8") as file_obj:
                    draft_info = json.load(file_obj)

                fixed_count = 0
                assets_root = Path(local_draft_dir) / "assets"

                def _normalize_path(material: Dict, subfolder: str) -> bool:
                    old_path = str(material.get("path", "")).strip()
                    filename = os.path.basename(old_path)
                    if not filename:
                        return False
                    new_path = assets_root / subfolder / filename
                    if new_path.exists() and str(new_path) != old_path:
                        material["path"] = str(new_path)
                        return True
                    return False

                # 修复视频路径
                videos = draft_info.get('materials', {}).get('videos', [])
                for video in videos:
                    subfolder = "images" if str(video.get("type", "")).lower() == "photo" else "videos"
                    if _normalize_path(video, subfolder):
                        fixed_count += 1
                        logger.debug(f"修复视频路径: {video.get('path')}")

                # 修复音频路径
                audios = draft_info.get('materials', {}).get('audios', [])
                for audio in audios:
                    if _normalize_path(audio, "audios"):
                        fixed_count += 1
                        logger.debug(f"修复音频路径: {audio.get('path')}")

                # 修复图片路径
                images = draft_info.get('materials', {}).get('images', [])
                for image in images:
                    if _normalize_path(image, "images"):
                        fixed_count += 1
                        logger.debug(f"修复图片路径: {image.get('path')}")

                if fixed_count > 0:
                    with open(info_path, "w", encoding="utf-8") as file_obj:
                        json.dump(draft_info, file_obj, ensure_ascii=False, indent=2)
                    logger.info(f"已修复 draft_info.json 中的 {fixed_count} 个文件路径")
            except json.JSONDecodeError:
                logger.warning(f"draft_info.json 格式异常，跳过修复")

        # 更新文件时间戳
        if content_path.exists():
            os.utime(content_path, None)
        if info_path.exists():
            os.utime(info_path, None)
        os.utime(local_draft_dir, None)

    def _postprocess_main_timeline_and_background(self, draft_duration: float) -> None:
        """将 mp4 轨道设为 main_track，并放到最底层时间线。"""
        _ = draft_duration
        get_local_draft_dir = getattr(self.capcut_service, "get_local_draft_dir", None)
        if not callable(get_local_draft_dir):
            return

        local_draft_dir = get_local_draft_dir()
        if not local_draft_dir:
            return

        for draft_path in [Path(local_draft_dir) / "draft_content.json", Path(local_draft_dir) / "draft_info.json"]:
            if draft_path.exists():
                self._fix_video_main_track_bottom(draft_path, Path(local_draft_dir))

    def _fix_video_main_track_bottom(self, content_path: Path, local_draft_dir: Path) -> None:
        """参考 capcut-mate 的轨道语义：将视频主轨命名为 main_track，并置于最底层时间线。"""
        with open(content_path, "r", encoding="utf-8") as file_obj:
            draft_content = json.load(file_obj)

        tracks = draft_content.get("tracks", [])
        video_tracks = [track for track in tracks if track.get("type") == "video"]
        if not video_tracks:
            return

        materials = draft_content.get("materials", {}).get("videos", [])
        material_map = {material.get("id"): material for material in materials}
        def _segment_material(segment: Dict) -> Dict:
            return material_map.get(segment.get("material_id"), {})

        def _segment_is_video(segment: Dict) -> bool:
            return str(_segment_material(segment).get("type", "")) == "video"

        source_track = None
        source_duration = -1
        for track in video_tracks:
            total = 0
            for segment in track.get("segments", []):
                if _segment_is_video(segment):
                    total += int((segment.get("target_timerange") or {}).get("duration") or 0)
            if total > source_duration:
                source_track = track
                source_duration = total

        if not source_track or source_duration <= 0:
            return

        changed = False
        # 将视频主轨标记为 main_track，其他同名轨道改名，避免“主轨消失/混乱”
        if source_track.get("name") != "main_track":
            source_track["name"] = "main_track"
            source_track["is_default_name"] = False
            changed = True

        for track in video_tracks:
            if track is source_track:
                continue
            if track.get("name") == "main_track":
                track["name"] = f"video_track_{track.get('id', '')[:8]}"
                changed = True

        # 把 main_track 放到视频轨道列表首位（最底层时间线）
        source_index = tracks.index(source_track)
        first_video_index = min(tracks.index(track) for track in video_tracks)
        if source_index != first_video_index:
            tracks.pop(source_index)
            tracks.insert(first_video_index, source_track)
            changed = True

        # 清理不含视频片段的重复主轨
        duplicate_main_tracks = [
            track for track in video_tracks
            if track is not source_track
            and track.get("name") == "main_track"
            and not any(_segment_is_video(segment) for segment in track.get("segments", []))
        ]
        if duplicate_main_tracks:
            draft_content["tracks"] = [track for track in tracks if track not in duplicate_main_tracks]
            changed = True

        if changed:
            with open(content_path, "w", encoding="utf-8") as file_obj:
                json.dump(draft_content, file_obj, ensure_ascii=False, indent=2)
            os.utime(content_path, None)
            os.utime(local_draft_dir, None)
            logger.info(f"已修正主轨为视频且置于最底层时间线: {content_path.name}")

    @staticmethod
    def _resolve_overlay_duration(config: Dict, total_duration: float, default_start: float = 0.0):
        """解析文案轨道的开始时间和持续时长。"""
        start = float(config.get("start", default_start))
        remaining = max(total_duration - start, 0.0)
        configured_duration = config.get("duration")
        if config.get("full_duration", False) or configured_duration in (None, "", 0, 0.0):
            return start, remaining

        return start, min(float(configured_duration), remaining)

    def _build_overlay_texts(self, duration: float, generated_title: Optional[str], video_layout: Optional[Dict] = None) -> List[Dict]:
        """构建标题、作者、身份等静态文案轨道。"""
        overlay_config = self.config.get("overlay_text", {})
        items: List[Dict] = []

        title_config = overlay_config.get("title", {})
        if title_config.get("enabled", True) and generated_title:
            title_start, title_duration = self._resolve_overlay_duration(title_config, duration, default_start=0.0)
            if title_duration > 0:
                title_font_size = int(title_config.get("font_size", 34))
                title_options = dict(title_config)
                if video_layout and title_config.get("anchor_to_video", True):
                    title_margin = float(title_config.get("margin_to_video", 96.0))
                    title_options["transform_y"] = video_layout["top"] - title_margin - (title_font_size / 2)

                items.append({
                    "name": "title",
                    "captions": [{
                        "start": int(title_start * 1_000_000),
                        "end": int((title_start + title_duration) * 1_000_000),
                        "text": generated_title,
                        "font_size": title_font_size,
                    }],
                    "options": self._build_caption_options(title_options),
                })

        author_config = overlay_config.get("author", {})
        if author_config.get("enabled", False):
            author_start, author_duration = self._resolve_overlay_duration(author_config, duration, default_start=0.0)
            if author_duration > 0:
                author_name = str(author_config.get("name", "")).strip()
                author_identity = str(author_config.get("identity", "")).strip()
                name_font_size = int(author_config.get("name_font_size", 22))
                identity_font_size = int(author_config.get("identity_font_size", 18))
                line_gap = float(author_config.get("line_gap", 28.0))
                base_author_y = None
                if video_layout and author_config.get("anchor_to_video", True):
                    base_author_y = video_layout["bottom"] + float(author_config.get("margin_to_video", 60.0))

                if author_name:
                    author_name_options = dict(author_config)
                    if base_author_y is not None:
                        author_name_options["name_transform_y"] = base_author_y + (name_font_size / 2)
                    items.append({
                        "name": "author_name",
                        "captions": [{
                            "start": int(author_start * 1_000_000),
                            "end": int((author_start + author_duration) * 1_000_000),
                            "text": author_name,
                            "font_size": name_font_size,
                        }],
                        "options": self._build_caption_options(author_name_options, prefix="name_"),
                    })

                if author_identity:
                    author_identity_options = dict(author_config)
                    if base_author_y is not None:
                        if author_name:
                            author_identity_options["identity_transform_y"] = base_author_y + (name_font_size / 2) + line_gap + (identity_font_size / 2)
                        else:
                            author_identity_options["identity_transform_y"] = base_author_y + (identity_font_size / 2)
                    items.append({
                        "name": "author_identity",
                        "captions": [{
                            "start": int(author_start * 1_000_000),
                            "end": int((author_start + author_duration) * 1_000_000),
                            "text": author_identity,
                            "font_size": identity_font_size,
                        }],
                        "options": self._build_caption_options(author_identity_options, prefix="identity_"),
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

    @staticmethod
    def _has_removed_segments(subtitle_data: SubtitleData) -> bool:
        """是否存在需要从时间轴中移除的片段。"""
        return any(segment.removed == 1 for segment in subtitle_data.segments)

    def _build_timeline_entries(self, subtitle_data: SubtitleData) -> List[Dict]:
        """将原始字幕时间轴映射到剪映目标时间轴，仅压缩被 removed 标记的时间。"""
        entries: List[Dict] = []
        removed_offset = 0.0

        for seg in subtitle_data.segments:
            duration = seg.end - seg.start
            if duration <= 0:
                logger.warning(f"跳过无效片段: id={seg.id}, start={seg.start}, end={seg.end}")
                continue

            if seg.removed == 1:
                logger.debug(f"跳过被移除的片段: {seg.start:.2f}s - {seg.end:.2f}s")
                removed_offset += duration
                continue

            target_start = max(seg.start - removed_offset, 0.0)
            target_end = max(seg.end - removed_offset, target_start)

            entries.append({
                "segment_id": seg.id,
                "text": seg.text,
                "keyword": seg.keyword,
                "keywords": list(seg.keywords),
                "text_grade": seg.text_grade,
                "video_grade": seg.video_grade,
                "source_start": seg.start,
                "source_end": seg.end,
                "target_start": target_start,
                "target_end": target_end,
            })

        total_duration = entries[-1]["target_end"] if entries else 0.0

        logger.info(f"构建了 {len(entries)} 条时间轴条目，压缩后总时长: {total_duration:.2f}秒")
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
                source_gap >= -merge_tolerance
                and target_gap >= -merge_tolerance
                and abs(source_gap - target_gap) <= merge_tolerance
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

    @staticmethod
    def _resolve_caption_keyword(entry: Dict) -> str:
        """优先使用主关键词，否则从命中的关键词中选择最长项高亮。"""
        text = str(entry.get("text", ""))
        primary_keyword = str(entry.get("keyword", "")).strip()
        if primary_keyword and primary_keyword in text:
            return primary_keyword

        matched_keywords = [keyword for keyword in entry.get("keywords", []) if keyword and keyword in text]
        if not matched_keywords:
            return ""

        return sorted(matched_keywords, key=len, reverse=True)[0]

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

            resolved_keyword = self._resolve_caption_keyword(entry)
            if resolved_keyword:
                # 仅用于视觉强调：将字幕中的关键词包裹双引号，不引入额外语义。
                quoted_keyword = f"\"{resolved_keyword}\""
                caption["text"] = str(caption["text"]).replace(resolved_keyword, quoted_keyword, 1)
                caption["keyword"] = quoted_keyword
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
                    material_source = material.local_path or material.download_url
                    if material.local_path:
                        normalized_path = self._ensure_capcut_compatible_broll_video(material.local_path)
                        material.processed_path = str(normalized_path)
                        material_source = material.processed_path
                    result = self.capcut_service.add_video_material(
                        material_source,
                        start_time,
                        duration
                    )
                elif material.type == "photo":
                    material_source = material.local_path or material.download_url
                    result = self.capcut_service.add_image_material(
                        material_source,
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
