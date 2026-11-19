"""
安全配置模块
集中管理安全相关的配置和工具
避免循环导入
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# 速率限制器 - 全局单例
limiter = Limiter(key_func=get_remote_address)
