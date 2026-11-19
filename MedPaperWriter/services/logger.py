"""
结构化日志模块
提供统一的日志记录功能，替代 print 调试
"""

import os
import sys
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class JSONFormatter(logging.Formatter):
    """JSON格式的日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


class Logger:
    """应用日志管理器"""

    _instances = {}

    def __new__(cls, name: str = "medtoolkit"):
        if name not in cls._instances:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instances[name] = instance
        return cls._instances[name]

    def __init__(self, name: str = "medtoolkit"):
        if self._initialized:
            return
        self._initialized = True

        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # 日志目录
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # 控制台处理器（人类可读格式）
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(module)s:%(lineno)d - %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)

        # 文件处理器（JSON格式）
        log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(file_handler)

        # 错误日志单独文件
        error_log_file = log_dir / f"error-{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        error_handler = logging.FileHandler(error_log_file, encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(error_handler)

    def debug(self, message: str, **extra):
        """记录 DEBUG 级别日志"""
        if extra:
            self.logger.debug(message, extra={"extra_data": extra})
        else:
            self.logger.debug(message)

    def info(self, message: str, **extra):
        """记录 INFO 级别日志"""
        if extra:
            self.logger.info(message, extra={"extra_data": extra})
        else:
            self.logger.info(message)

    def warning(self, message: str, **extra):
        """记录 WARNING 级别日志"""
        if extra:
            self.logger.warning(message, extra={"extra_data": extra})
        else:
            self.logger.warning(message)

    def error(self, message: str, exc_info: bool = True, **extra):
        """记录 ERROR 级别日志"""
        if extra:
            self.logger.error(message, extra={"extra_data": extra}, exc_info=exc_info)
        else:
            self.logger.error(message, exc_info=exc_info)

    def critical(self, message: str, exc_info: bool = True, **extra):
        """记录 CRITICAL 级别日志"""
        if extra:
            self.logger.critical(message, extra={"extra_data": extra}, exc_info=exc_info)
        else:
            self.logger.critical(message, exc_info=exc_info)


# 全局日志实例
logger = Logger()
