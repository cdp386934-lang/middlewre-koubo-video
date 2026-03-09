#!/usr/bin/env python3
"""
草稿管理工具 - 查看和导出 CapCut-mate 生成的草稿
"""

import requests
import json
import sys
from pathlib import Path


def get_draft_info(draft_id: str, api_url: str = "http://localhost:30000"):
    """获取草稿信息"""
    url = f"{api_url}/openapi/capcut-mate/v1/get_draft"
    params = {"draft_id": draft_id}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ 获取草稿信息失败: {e}")
        return None


def save_draft(draft_url: str, api_url: str = "http://localhost:30000"):
    """保存草稿到剪映目录"""
    url = f"{api_url}/openapi/capcut-mate/v1/save_draft"
    data = {"draft_url": draft_url}

    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ 保存草稿失败: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("用法: python draft_manager.py <draft_id>")
        print("示例: python draft_manager.py 202603091844518f128738")
        sys.exit(1)

    draft_id = sys.argv[1]

    print(f"📋 查询草稿信息: {draft_id}")
    print("=" * 60)

    # 获取草稿信息
    info = get_draft_info(draft_id)
    if not info:
        sys.exit(1)

    if info.get("code") != 0:
        print(f"❌ 错误: {info.get('message')}")
        sys.exit(1)

    files = info.get("files", [])
    print(f"✅ 草稿生成成功！")
    print(f"📁 包含 {len(files)} 个文件")
    print()

    # 分类显示文件
    config_files = [f for f in files if f.endswith('.json') or f.endswith('.tmp')]
    video_files = [f for f in files if '/videos/' in f]
    audio_files = [f for f in files if '/audios/' in f]

    print(f"📄 配置文件: {len(config_files)} 个")
    for f in config_files[:5]:
        filename = f.split('/')[-1]
        print(f"   - {filename}")
    if len(config_files) > 5:
        print(f"   ... 还有 {len(config_files) - 5} 个")

    print()
    print(f"🎬 视频片段: {len(video_files)} 个")
    if video_files:
        print(f"   (由于去气口处理，视频被分成了多个片段)")

    if audio_files:
        print()
        print(f"🎵 音频文件: {len(audio_files)} 个")

    print()
    print("=" * 60)
    print("📌 如何使用草稿：")
    print()
    print("方式1：在剪映专业版中查看")
    print("   1. 打开剪映专业版")
    print("   2. 在草稿列表中查找最新的草稿")
    print("   3. 草稿名称应该是：未加工")
    print()
    print("方式2：通过 CapCut-mate 导出")
    draft_url = f"https://capcut-mate.jcaigc.cn/openapi/capcut-mate/v1/get_draft?draft_id={draft_id}"
    print(f"   草稿 URL: {draft_url}")
    print()
    print("💡 提示：")
    print("   - 草稿已经生成在 CapCut-mate 的输出目录")
    print("   - 包含了去气口处理后的视频片段")
    print("   - 包含了 AI 生成的字幕")
    print("   - 可以直接在剪映中编辑")


if __name__ == "__main__":
    main()
