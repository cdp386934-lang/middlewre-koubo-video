import http.server
import socketserver
import threading
from pathlib import Path
from typing import Union
from loguru import logger


class LocalFileServer:
    """本地文件服务器，用于为 CapCut-mate API 提供文件访问"""

    def __init__(self, directory: str, port: int = 8000):
        self.directory = Path(directory).absolute()
        self.port = port
        self.server = None
        self.thread = None
        self.base_url = f"http://localhost:{port}"

    def start(self):
        """启动文件服务器"""
        if self.server is not None:
            logger.warning("文件服务器已经在运行")
            return

        directory = self.directory

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(directory), **kwargs)

            def log_message(self, format, *args):
                # 禁用默认日志输出
                pass

        try:
            self.server = socketserver.TCPServer(("", self.port), Handler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info(f"本地文件服务器已启动: {self.base_url}")
        except Exception as e:
            logger.error(f"启动文件服务器失败: {e}")
            raise

    def stop(self):
        """停止文件服务器"""
        if self.server:
            self.server.shutdown()
            self.server = None
            logger.info("本地文件服务器已停止")

    def get_file_url(self, file_path: Union[str, Path]) -> str:
        """
        获取文件的 HTTP URL

        Args:
            file_path: 文件路径（绝对路径或相对于服务器目录的路径）

        Returns:
            str: 文件的 HTTP URL
        """
        file_path = Path(file_path).absolute()
        try:
            relative_path = file_path.relative_to(self.directory)
            url = f"{self.base_url}/{relative_path}"
            return url
        except ValueError:
            logger.error(f"文件不在服务器目录中: {file_path}")
            raise ValueError(f"文件必须在 {self.directory} 目录下")
