"""
统一配置管理模块
集中管理所有应用配置，支持环境变量覆盖
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Settings:
    """应用配置类 - 单例模式"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # === 项目路径 ===
        self.BASE_DIR = Path(__file__).parent.parent

        # === LLM 配置 ===
        self.LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
        self.LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
        self.LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")
        self.LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4000"))

        # === 服务器配置 ===
        self.HOST: str = os.getenv("HOST", "0.0.0.0")
        self.PORT: int = int(os.getenv("PORT", "8001"))
        self.DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

        # === 速率限制 ===
        self.RATE_LIMIT_WINDOW: int = 60  # 时间窗口（秒）
        self.RATE_LIMIT_MAX_REQUESTS: int = 30  # 窗口内最大请求数

        # === 文件上传 ===
        self.MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
        self.MAX_REFERENCES: int = 10  # 最大参考资料数
        self.ALLOWED_EXTENSIONS: set = {'.txt', '.md', '.docx', '.xlsx', '.csv', '.pdf'}

        # === 会话管理 ===
        self.SESSION_DATA_DIR: Path = self.BASE_DIR / "data" / "sessions"
        self.MAX_QA_CONTEXT_LENGTH: int = 50  # 最大QA上下文轮数

        # === 日志配置 ===
        self.LOG_DIR: Path = self.BASE_DIR / "logs"
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

        # === 导出配置 ===
        self.EXPORT_DIR: Path = self.BASE_DIR / "data" / "exports"

        # === 安全配置 ===
        self.CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")
        self.CSP_POLICY: str = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:; style-src 'self' 'unsafe-inline';"

    def validate(self) -> list:
        """验证配置是否有效，返回缺失的配置项列表"""
        missing = []
        if not self.LLM_API_KEY:
            missing.append("LLM_API_KEY")
        return missing


# 全局配置实例
settings = Settings()
