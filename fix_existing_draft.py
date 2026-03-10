#!/usr/bin/env python3
"""修复已存在的草稿文件路径"""

import json
import os
from pathlib import Path

def fix_draft_paths(draft_id: str):
    """修复指定草稿的文件路径"""
    draft_root = Path.home() / "Library/Containers/com.lemon.lvpro/Data/Movies/JianyingPro/User Data/Projects/com.lveditor.draft"
    local_draft_dir = draft_root / draft_id

    if not local_draft_dir.exists():
        print(f"草稿目录不存在: {local_draft_dir}")
        return False

    print(f"开始修复草稿: {draft_id}")

    # 修复 draft_content.json
    content_path = local_draft_dir / "draft_content.json"
    if content_path.exists():
        print(f"修复 draft_content.json...")
        with open(content_path, "r", encoding="utf-8") as f:
            draft_content = json.load(f)

        fixed_count = 0

        # 修复视频路径
        videos = draft_content.get('materials', {}).get('videos', [])
        for video in videos:
            old_path = video.get('path', '')
            if old_path and ('/capcut-mate/output/draft/' in old_path or '/localhost:' in old_path or 'http://' in old_path):
                filename = os.path.basename(old_path)
                # 检查是图片还是视频
                if filename.endswith(('.png', '.jpg', '.jpeg')):
                    new_path = str(local_draft_dir / 'assets' / 'images' / filename)
                else:
                    new_path = str(local_draft_dir / 'assets' / 'videos' / filename)
                if os.path.exists(new_path):
                    print(f"  修复视频/图片路径: {filename}")
                    video['path'] = new_path
                    fixed_count += 1

        # 修复音频路径
        audios = draft_content.get('materials', {}).get('audios', [])
        for audio in audios:
            old_path = audio.get('path', '')
            if old_path and '/capcut-mate/output/draft/' in old_path:
                filename = os.path.basename(old_path)
                new_path = str(local_draft_dir / 'assets' / 'audios' / filename)
                if os.path.exists(new_path):
                    print(f"  修复音频路径: {filename}")
                    audio['path'] = new_path
                    fixed_count += 1

        if fixed_count > 0:
            with open(content_path, "w", encoding="utf-8") as f:
                json.dump(draft_content, f, ensure_ascii=False, indent=2)
            print(f"  已修复 draft_content.json 中的 {fixed_count} 个路径")

    # 修复 draft_info.json
    info_path = local_draft_dir / "draft_info.json"
    if info_path.exists():
        print(f"修复 draft_info.json...")
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                draft_info = json.load(f)

            fixed_count = 0

            # 修复视频路径
            videos = draft_info.get('materials', {}).get('videos', [])
            for video in videos:
                old_path = video.get('path', '')
                if old_path and ('/capcut-mate/output/draft/' in old_path or '/localhost:' in old_path or 'http://' in old_path):
                    filename = os.path.basename(old_path)
                    # 检查是图片还是视频
                    if filename.endswith(('.png', '.jpg', '.jpeg')):
                        new_path = str(local_draft_dir / 'assets' / 'images' / filename)
                    else:
                        new_path = str(local_draft_dir / 'assets' / 'videos' / filename)
                    if os.path.exists(new_path):
                        print(f"  修复视频/图片路径: {filename}")
                        video['path'] = new_path
                        fixed_count += 1

            # 修复音频路径
            audios = draft_info.get('materials', {}).get('audios', [])
            for audio in audios:
                old_path = audio.get('path', '')
                if old_path and ('/capcut-mate/output/draft/' in old_path or '/localhost:' in old_path or 'http://' in old_path):
                    filename = os.path.basename(old_path)
                    new_path = str(local_draft_dir / 'assets' / 'audios' / filename)
                    if os.path.exists(new_path):
                        print(f"  修复音频路径: {filename}")
                        audio['path'] = new_path
                        fixed_count += 1

            if fixed_count > 0:
                with open(info_path, "w", encoding="utf-8") as f:
                    json.dump(draft_info, f, ensure_ascii=False, indent=2)
                print(f"  已修复 draft_info.json 中的 {fixed_count} 个路径")
        except json.JSONDecodeError:
            print(f"  draft_info.json 格式异常（可能是base64编码），跳过修复")

    # 更新文件时间戳
    if content_path.exists():
        os.utime(content_path, None)
    if info_path.exists():
        os.utime(info_path, None)
    os.utime(local_draft_dir, None)

    print(f"草稿修复完成: {draft_id}")
    return True


if __name__ == "__main__":
    # 修复最新的草稿
    draft_id = "20260310105851475a01d0"
    fix_draft_paths(draft_id)
