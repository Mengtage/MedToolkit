"""
配置模块
"""

__all__ = ["limiter", "settings"]


def __getattr__(name):
    # 懒加载，避免仅导入 settings 时也拉起 slowapi
    if name == "limiter":
        from config.security import limiter
        return limiter
    if name == "settings":
        from config.settings import settings
        return settings
    raise AttributeError(f"module 'config' has no attribute {name!r}")
