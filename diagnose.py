#!/usr/bin/env python3
"""诊断脚本：检查草稿生成的问题"""

import json
import requests
from pathlib import Path

# 检查 capcut-mate API 是否正常
def check_capcut_api():
    print("=" * 60)
    print("检查 CapCut-mate API")
    print("=" * 60)

    api_url = "http://localhost:30000"

    try:
        # 测试 API 连接
        response = requests.get(f"{api_url}/openapi/capcut-mate/v1/health", timeout=5)
        if response.status_code == 200:
            print("✓ CapCut-mate API 正常运行")
        else:
            print(f"✗ CapCut-mate API 返回异常状态码: {response.status_code}")
    except Exception as e:
        print(f"✗ CapCut-mate API 连接失败: {e}")
        print("  请确保 capcut-mate 服务已启动")
        return False

    return True

# 检查文件服务器
def check_file_server():
    print("\n" + "=" * 60)
    print("检查本地文件服务器")
    print("=" * 60)

    file_server_url = "http://localhost:8000"

    try:
        response = requests.get(file_server_url, timeout=5)
        if response.status_code == 200:
            print("✓ 本地文件服务器正常运行")
        else:
            print(f"✗ 本地文件服务器返回异常状态码: {response.status_code}")
    except Exception as e:
        print(f"✗ 本地文件服务器连接失败: {e}")
        return False

    return True

# 检查最新草稿
def check_latest_draft():
    print("\n" + "=" * 60)
    print("检查最新草稿")
    print("=" * 60)

    metadata_dir = Path("output/drafts")
    if not metadata_dir.exists():
        print("✗ 草稿目录不存在")
        return

    metadata_files = list(metadata_dir.glob("*_metadata.json"))
    if not metadata_files:
        print("✗ 未找到草稿元数据文件")
        return

    # 获取最新的元数据文件
    latest_metadata = max(metadata_files, key=lambda p: p.stat().st_mtime)
    print(f"最新草稿元数据: {latest_metadata.name}")

    with open(latest_metadata, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    print(f"\n草稿信息:")
    print(f"  草稿 ID: {metadata.get('draft_id')}")
    print(f"  草稿名称: {metadata.get('draft_name')}")
    print(f"  视频路径: {metadata.get('video_path')}")
    print(f"  分辨率: {metadata.get('resolution')}")
    print(f"  时长: {metadata.get('duration')}秒")
    print(f"  有字幕: {metadata.get('has_subtitles')}")
    print(f"  有BGM: {metadata.get('has_bgm')}")
    print(f"  关键词数量: {metadata.get('keyword_count')}")
    print(f"  生成的标题: {metadata.get('generated_title')}")
    print(f"  作者名称: {metadata.get('author_name')}")
    print(f"  作者身份: {metadata.get('author_identity')}")

# 检查配置
def check_config():
    print("\n" + "=" * 60)
    print("检查配置文件")
    print("=" * 60)

    import yaml
    config_path = Path("config/config.yaml")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 检查作者配置
    author_config = config.get("overlay_text", {}).get("author", {})
    print(f"\n作者配置:")
    print(f"  启用: {author_config.get('enabled')}")
    print(f"  名称: {author_config.get('name') or '(未设置)'}")
    print(f"  身份: {author_config.get('identity') or '(未设置)'}")

    if not author_config.get('enabled'):
        print("\n⚠️  作者信息未启用，需要在 config.yaml 中设置:")
        print("     overlay_text.author.enabled: true")
        print("     overlay_text.author.name: '你的名字'")
        print("     overlay_text.author.identity: '你的身份'")

if __name__ == "__main__":
    check_capcut_api()
    check_file_server()
    check_latest_draft()
    check_config()

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)
