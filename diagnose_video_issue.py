#!/usr/bin/env python3
"""诊断视频添加失败的问题"""

import json
import sys
from pathlib import Path
import requests

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.file_server import LocalFileServer

def main():
    print("=" * 60)
    print("诊断视频添加失败问题")
    print("=" * 60)

    # 1. 检查视频文件
    project_root = Path(__file__).parent
    input_video = project_root / "input" / "未加工.mp4"
    temp_video = project_root / "temp" / "未加工_capcut_ready.mp4"

    print("\n1. 检查视频文件:")
    print(f"   原始视频: {input_video}")
    print(f"   存在: {input_video.exists()}")
    if input_video.exists():
        print(f"   大小: {input_video.stat().st_size / 1024 / 1024:.2f} MB")

    print(f"\n   转码视频: {temp_video}")
    print(f"   存在: {temp_video.exists()}")
    if temp_video.exists():
        print(f"   大小: {temp_video.stat().st_size / 1024 / 1024:.2f} MB")

    # 2. 测试文件服务器
    print("\n2. 测试文件服务器:")
    file_server = LocalFileServer(directory=str(project_root), port=8001)

    try:
        file_server.start()
        print(f"   文件服务器已启动: {file_server.base_url}")

        # 测试生成URL
        test_video = temp_video if temp_video.exists() else input_video
        if test_video.exists():
            try:
                video_url = file_server.get_file_url(test_video)
                print(f"   视频URL: {video_url}")

                # 测试访问URL
                response = requests.get(video_url, timeout=5, stream=True)
                print(f"   URL访问状态: {response.status_code}")
                print(f"   Content-Type: {response.headers.get('Content-Type')}")
                print(f"   Content-Length: {response.headers.get('Content-Length')}")

            except Exception as e:
                print(f"   ❌ 生成URL失败: {e}")
        else:
            print("   ⚠️  没有找到视频文件")

    except Exception as e:
        print(f"   ❌ 文件服务器启动失败: {e}")
    finally:
        file_server.stop()

    # 3. 检查CapCut API
    print("\n3. 检查CapCut API:")
    capcut_api = "http://localhost:30000"
    try:
        response = requests.get(f"{capcut_api}/health", timeout=5)
        print(f"   API状态: {response.status_code}")
    except Exception as e:
        print(f"   ❌ API连接失败: {e}")

    # 4. 检查草稿元数据
    print("\n4. 检查草稿元数据:")
    metadata_file = project_root / "output" / "drafts" / "未加工_metadata.json"
    if metadata_file.exists():
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        print(f"   草稿ID: {metadata.get('draft_id')}")
        print(f"   视频路径: {metadata.get('video_path')}")
    else:
        print("   ⚠️  元数据文件不存在")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
