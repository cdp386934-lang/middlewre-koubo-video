#!/usr/bin/env python3
"""
测试脚本 - 验证项目结构和依赖
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    """测试模块导入"""
    print("测试模块导入...")

    try:
        # 测试数据模型
        from src.models.subtitle import SubtitleData, SubtitleSegment
        from src.models.keyword import Keyword, KeywordData
        from src.models.draft import DraftMetadata
        print("✓ 数据模型导入成功")

        # 测试工具模块
        from src.utils.logger import setup_logger
        from src.utils.file_handler import ensure_dir, read_json, write_json
        print("✓ 工具模块导入成功")

        # 测试服务模块
        from src.services.whisper_service import WhisperService
        from src.services.deepseek_service import DeepSeekService
        from src.services.capcut_service import CapCutService
        print("✓ 服务模块导入成功")

        # 测试处理模块
        from src.modules.video_to_audio import VideoToAudioConverter
        from src.modules.asr import ASRModule
        from src.modules.breath_removal import BreathRemovalModule
        from src.modules.keyword_extractor import KeywordExtractor
        from src.modules.material_manager import MaterialManager
        from src.modules.bgm_manager import BGMManager
        from src.modules.video_info import VideoInfoExtractor
        from src.modules.draft_generator import DraftGenerator
        print("✓ 处理模块导入成功")

        # 测试工作流
        from src.pipeline import VideoPipeline
        print("✓ 工作流模块导入成功")

        print("\n✓ 所有模块导入测试通过！")
        return True

    except ImportError as e:
        print(f"\n✗ 模块导入失败: {e}")
        return False


def test_config():
    """测试配置文件"""
    print("\n测试配置文件...")

    try:
        import yaml
        config_path = project_root / "config" / "config.yaml"

        if not config_path.exists():
            print(f"✗ 配置文件不存在: {config_path}")
            return False

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        required_keys = ["paths", "whisper", "deepseek", "capcut", "subtitle", "keyword", "logging"]
        for key in required_keys:
            if key not in config:
                print(f"✗ 配置缺少必需项: {key}")
                return False

        print("✓ 配置文件验证通过")
        return True

    except Exception as e:
        print(f"✗ 配置文件验证失败: {e}")
        return False


def test_directories():
    """测试目录结构"""
    print("\n测试目录结构...")

    required_dirs = [
        "config",
        "src/modules",
        "src/services",
        "src/models",
        "src/utils",
        "input",
        "output/audio",
        "output/subtitles",
        "output/keywords",
        "output/drafts",
        "temp",
        "logs"
    ]

    all_exist = True
    for dir_path in required_dirs:
        full_path = project_root / dir_path
        if not full_path.exists():
            print(f"✗ 目录不存在: {dir_path}")
            all_exist = False

    if all_exist:
        print("✓ 目录结构验证通过")

    return all_exist


def main():
    """主测试函数"""
    print("=" * 60)
    print("middleware-koubo-video 项目验证")
    print("=" * 60)

    results = []
    results.append(("模块导入", test_imports()))
    results.append(("配置文件", test_config()))
    results.append(("目录结构", test_directories()))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name}: {status}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n✓ 所有测试通过！项目结构正确。")
        print("\n下一步:")
        print("1. 安装依赖: pip install -r requirements.txt")
        print("2. 配置 API Key: 编辑 .env 文件")
        print("3. 运行程序: python src/main.py")
    else:
        print("\n✗ 部分测试失败，请检查项目结构。")
        sys.exit(1)


if __name__ == "__main__":
    main()
