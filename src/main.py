import os
import sys
from pathlib import Path
from typing import Union
import yaml
from dotenv import load_dotenv
from loguru import logger

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.pipeline import VideoPipeline
from src.utils.logger import setup_logger


def load_config(config_path: Union[str, Path]) -> dict:
    """加载配置文件"""
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config


def main():
    """主入口函数"""
    # 加载环境变量
    load_dotenv()

    # 加载配置
    config_path = project_root / "config" / "config.yaml"
    config = load_config(config_path)

    # 设置日志
    setup_logger(config)

    logger.info("=" * 60)
    logger.info("middleware-koubo-video 视频处理中间件")
    logger.info("=" * 60)

    # 获取输入视频路径
    input_dir = Path(config["paths"]["input"])
    video_files = list(input_dir.glob("*.mp4"))

    if not video_files:
        logger.error(f"未找到输入视频文件: {input_dir}")
        return

    input_video = video_files[0]
    logger.info(f"输入视频: {input_video}")

    try:
        # 创建工作流
        pipeline = VideoPipeline(config)

        # 执行处理
        draft_metadata = pipeline.run(input_video)

        logger.info("✓ 处理成功完成！")
        logger.info(f"✓ 草稿已生成，可在剪映中打开")
        logger.info(f"✓ 草稿名称: {draft_metadata.draft_name}")
        logger.info(f"✓ 字幕数量: {len(draft_metadata.draft_path) if draft_metadata.has_subtitles else 0}")
        logger.info(f"✓ 关键词数量: {draft_metadata.keyword_count}")

    except Exception as e:
        logger.error(f"✗ 处理失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
