#!/usr/bin/env python3
"""修复草稿文件中的路径问题"""

import json
import os
import sys
from pathlib import Path

def fix_draft_paths(draft_id: str):
    """修复指定草稿的文件路径"""

    draft_root = Path.home() / "Library/Containers/com.lemon.lvpro/Data/Movies/JianyingPro/User Data/Projects/com.lveditor.draft"
    draft_dir = draft_root / draft_id

    if not draft_dir.exists():
        print(f"✗ 草稿目录不存在: {draft_dir}")
        return False

    draft_content_path = draft_dir / "draft_content.json"
    if not draft_content_path.exists():
        print(f"✗ 草稿内容文件不存在: {draft_content_path}")
        return False

    print(f"正在修复草稿: {draft_id}")
    print(f"草稿路径: {draft_dir}")

    # 读取草稿内容
    with open(draft_content_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 备份原文件
    backup_path = draft_content_path.with_suffix('.json.backup')
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✓ 已备份原文件: {backup_path}")

    # 修复视频路径
    videos = data.get('materials', {}).get('videos', [])
    fixed_count = 0

    for video in videos:
        old_path = video.get('path', '')
        if old_path and '/capcut-mate/output/draft/' in old_path:
            # 提取文件名
            filename = os.path.basename(old_path)
            # 构建新路径（相对路径）
            new_path = str(draft_dir / 'assets' / 'videos' / filename)

            if os.path.exists(new_path):
                video['path'] = new_path
                print(f"✓ 修复视频路径: {filename}")
                fixed_count += 1
            else:
                print(f"✗ 文件不存在: {new_path}")

    # 修复音频路径（如果有）
    audios = data.get('materials', {}).get('audios', [])
    for audio in audios:
        old_path = audio.get('path', '')
        if old_path and '/capcut-mate/output/draft/' in old_path:
            filename = os.path.basename(old_path)
            new_path = str(draft_dir / 'assets' / 'audios' / filename)

            if os.path.exists(new_path):
                audio['path'] = new_path
                print(f"✓ 修复音频路径: {filename}")
                fixed_count += 1

    # 保存修复后的文件
    if fixed_count > 0:
        with open(draft_content_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n✓ 已修复 {fixed_count} 个文件路径")
        print(f"✓ 草稿文件已更新: {draft_content_path}")
        return True
    else:
        print("\n⚠️  没有需要修复的路径")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # 查找最新的草稿
        draft_root = Path.home() / "Library/Containers/com.lemon.lvpro/Data/Movies/JianyingPro/User Data/Projects/com.lveditor.draft"
        drafts = [d for d in draft_root.iterdir() if d.is_dir() and d.name.startswith('202')]

        if not drafts:
            print("✗ 未找到草稿")
            sys.exit(1)

        # 按修改时间排序，获取最新的
        latest_draft = max(drafts, key=lambda d: d.stat().st_mtime)
        draft_id = latest_draft.name
        print(f"使用最新草稿: {draft_id}\n")
    else:
        draft_id = sys.argv[1]

    success = fix_draft_paths(draft_id)
    sys.exit(0 if success else 1)
