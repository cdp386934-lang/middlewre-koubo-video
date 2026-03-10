#!/usr/bin/env python3
"""重新生成草稿，修复所有路径和样式问题"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from src.pipeline import Pipeline
from src.utils.config_loader import load_config

def main():
    # 加载配置
    config = load_config(str(project_root / "config/config.yaml"))

    # 创建 pipeline
    pipeline = Pipeline(config)

    # 指定输入视频
    video_path = str(project_root / "input/未加工.mp4")

    print(f"开始处理视频: {video_path}")
    print("=" * 60)

    # 运行完整流程
    result = pipeline.run(video_path)

    print("=" * 60)
    print(f"处理完成！")
    print(f"草稿ID: {result.draft_metadata.draft_id}")
    print(f"草稿路径: {result.draft_metadata.draft_path}")

    return result

if __name__ == "__main__":
    main()
