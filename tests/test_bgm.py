#!/usr/bin/env python3
"""
BGM 功能测试脚本
用于验证 BGM 配置加载和数据模型
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.bgm import BGMSegment, BGMData
from loguru import logger


def test_bgm_segment():
    """测试 BGMSegment 模型"""
    logger.info("=== 测试 BGMSegment 模型 ===")

    # 测试1: 正常片段
    try:
        segment = BGMSegment(
            path="assets/bgm/test.mp3",
            start=0.0,
            end=10.0,
            volume=0.5
        )
        logger.success(f"✓ 正常片段创建成功: {segment}")
    except Exception as e:
        logger.error(f"✗ 正常片段创建失败: {e}")

    # 测试2: end=None
    try:
        segment = BGMSegment(
            path="assets/bgm/test.mp3",
            start=0.0,
            end=None
        )
        logger.success(f"✓ end=None 片段创建成功: {segment}")
    except Exception as e:
        logger.error(f"✗ end=None 片段创建失败: {e}")

    # 测试3: 无效的 end 时间（应该失败）
    try:
        segment = BGMSegment(
            path="assets/bgm/test.mp3",
            start=10.0,
            end=5.0  # end < start
        )
        logger.error(f"✗ 应该失败但成功了: {segment}")
    except ValueError as e:
        logger.success(f"✓ 正确捕获无效 end 时间: {e}")

    # 测试4: 无效的音量（应该失败）
    try:
        segment = BGMSegment(
            path="assets/bgm/test.mp3",
            start=0.0,
            end=10.0,
            volume=3.0  # volume > 2.0
        )
        logger.error(f"✗ 应该失败但成功了: {segment}")
    except ValueError as e:
        logger.success(f"✓ 正确捕获无效音量: {e}")


def test_bgm_data():
    """测试 BGMData 模型"""
    logger.info("\n=== 测试 BGMData 模型 ===")

    # 测试1: 正常配置
    try:
        bgm_data = BGMData(
            enabled=True,
            default_volume=0.3,
            segments=[
                BGMSegment(path="assets/bgm/intro.mp3", start=0.0, end=10.0, volume=0.5),
                BGMSegment(path="assets/bgm/main.mp3", start=10.0, end=60.0),
                BGMSegment(path="assets/bgm/outro.mp3", start=60.0, end=None, volume=0.4),
            ]
        )
        logger.success(f"✓ BGMData 创建成功，包含 {len(bgm_data.segments)} 个片段")

        # 测试 get_effective_volume
        for i, segment in enumerate(bgm_data.segments):
            volume = bgm_data.get_effective_volume(segment)
            logger.info(f"  片段 {i+1}: {segment.path}, 有效音量: {volume}")
    except Exception as e:
        logger.error(f"✗ BGMData 创建失败: {e}")

    # 测试2: 空片段列表
    try:
        bgm_data = BGMData(enabled=False, default_volume=0.3, segments=[])
        logger.success(f"✓ 空片段列表创建成功")
    except Exception as e:
        logger.error(f"✗ 空片段列表创建失败: {e}")

    # 测试3: 无效的默认音量（应该失败）
    try:
        bgm_data = BGMData(enabled=True, default_volume=5.0, segments=[])
        logger.error(f"✗ 应该失败但成功了")
    except ValueError as e:
        logger.success(f"✓ 正确捕获无效默认音量: {e}")


def test_yaml_config():
    """测试从 YAML 配置加载"""
    logger.info("\n=== 测试 YAML 配置加载 ===")

    import yaml

    # 模拟 YAML 配置
    yaml_config = """
bgm:
  enabled: true
  default_volume: 0.3
  segments:
    - path: "assets/bgm/intro.mp3"
      start: 0.0
      end: 10.0
      volume: 0.5
    - path: "assets/bgm/main.mp3"
      start: 10.0
      end: 60.0
    - path: "assets/bgm/outro.mp3"
      start: 60.0
      end: null
      volume: 0.4
"""

    try:
        config = yaml.safe_load(yaml_config)
        bgm_config = config.get("bgm")
        bgm_data = BGMData(**bgm_config)
        logger.success(f"✓ 从 YAML 加载成功，包含 {len(bgm_data.segments)} 个片段")

        for i, segment in enumerate(bgm_data.segments):
            logger.info(f"  片段 {i+1}:")
            logger.info(f"    路径: {segment.path}")
            logger.info(f"    时间: {segment.start}s - {segment.end}s")
            logger.info(f"    音量: {bgm_data.get_effective_volume(segment)}")
    except Exception as e:
        logger.error(f"✗ 从 YAML 加载失败: {e}")


if __name__ == "__main__":
    logger.info("开始 BGM 功能测试\n")

    test_bgm_segment()
    test_bgm_data()
    test_yaml_config()

    logger.info("\n测试完成！")
