import sys
from loguru import logger
from pathlib import Path


def setup_logger(config: dict):
    """设置日志系统"""
    log_config = config.get("logging", {})
    log_dir = Path(config["paths"]["logs"])
    log_dir.mkdir(parents=True, exist_ok=True)

    # 移除默认处理器
    logger.remove()

    # 添加控制台处理器
    logger.add(
        sys.stdout,
        format=log_config.get("format", "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"),
        level=log_config.get("level", "INFO"),
        colorize=True
    )

    # 添加文件处理器
    logger.add(
        log_dir / "app.log",
        format=log_config.get("format", "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"),
        level=log_config.get("level", "INFO"),
        rotation=log_config.get("rotation", "10 MB"),
        retention=log_config.get("retention", "7 days"),
        encoding="utf-8"
    )

    return logger
