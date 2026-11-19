"""
安全配置模块
集中管理安全相关的配置和工具
避免循环导入

slowapi 为可选依赖：未安装时 limiter 退化为空实现，
保证主应用在最小依赖下仍可启动（速率限制本身由 app.py 的中间件承担）。
"""

try:  # pragma: no cover - 依赖可用性分支
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address)
    LIMITER_AVAILABLE = True
except Exception:  # pragma: no cover
    class _NoopLimiter:
        """未安装 slowapi 时的占位实现，仅保证导入与属性访问不报错"""

        enabled = False

        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        def __getattr__(self, item):
            return lambda *a, **k: None

    limiter = _NoopLimiter()
    LIMITER_AVAILABLE = False
