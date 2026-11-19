"""
FastAPI应用入口
MedPaperWriter - 医学论文自动化写作系统
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path
import time
from collections import defaultdict

from api import routes_mode, routes_chat, routes_review, routes_export
from services.session_manager import manager
from services.logger import logger
from config.settings import settings

app = FastAPI(
    title="MedPaperWriter - 医学论文自动化写作系统",
    description="支持综述模式和RCT模式的医学论文自动生成工具",
    version="1.0.0"
)


# 简单的速率限制器
class RateLimiter:
    """简单的内存速率限制器"""
    
    def __init__(self):
        self.requests = defaultdict(list)
        self.window = 60  # 时间窗口（秒）
        self.max_requests = 30  # 时间窗口内最大请求数
    
    def is_allowed(self, client_id: str) -> bool:
        """检查是否允许请求"""
        now = time.time()
        
        # 清理过期请求
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if now - req_time < self.window
        ]
        
        # 检查是否超限
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        # 记录请求
        self.requests[client_id].append(now)
        return True

rate_limiter = RateLimiter()

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 安全响应头 + 速率限制中间件
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # 获取客户端IP作为标识
    client_ip = request.client.host if request.client else "unknown"
    
    # 对API请求应用速率限制
    if request.url.path.startswith("/api/"):
        if not rate_limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": "请求过于频繁，请稍后再试"
                }
            )
    
    # 添加安全响应头
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:; style-src 'self' 'unsafe-inline';"
    return response

# 获取项目根目录
BASE_DIR = Path(__file__).parent

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# 处理Vite客户端请求（防止404错误）
@app.api_route("/@vite/client", methods=["GET", "POST", "OPTIONS", "HEAD"])
async def vite_client():
    return Response(content="", media_type="application/javascript")

# 配置模板
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# 注册路由
app.include_router(routes_mode.router, prefix="/api/mode", tags=["模式选择"])
app.include_router(routes_chat.router, prefix="/api/chat", tags=["对话交互"])
app.include_router(routes_review.router, prefix="/api/review", tags=["审核流程"])
app.include_router(routes_export.router, prefix="/api/export", tags=["文档导出"])


@app.get("/", response_class=HTMLResponse)
async def home():
    """主界面"""
    return FileResponse(str(BASE_DIR / "templates" / "index.html"))


@app.get("/app")
async def app_page():
    """返回主应用页面"""
    return FileResponse(str(BASE_DIR / "templates" / "index.html"))


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "MedPaperWriter"}


@app.get("/api/session/{session_id}")
async def get_session(session_id: str, user_token: str = None):
    """获取会话状态（使用安全数据暴露）"""
    session = manager.get_session(session_id, user_token)
    if session:
        # 仅返回必要信息，保护敏感数据
        return JSONResponse({
            "success": True,
            "data": session.to_safe_dict()
        })
    return JSONResponse({
        "success": False,
        "message": "会话不存在或无权限访问"
    }, status_code=404)


@app.get("/api/session/active")
async def get_active_session():
    """获取当前活跃会话"""
    session = manager.get_active_session()
    if session:
        # 仅返回必要信息，保护敏感数据
        return JSONResponse({
            "success": True,
            "data": session.to_safe_dict()
        })
    return JSONResponse({
        "success": False,
        "message": "无活跃会话"
    })


@app.post("/api/session/terminate/{session_id}")
async def terminate_session(session_id: str, user_token: str = None):
    """终止会话（验证用户令牌）"""
    # 验证用户令牌
    if not manager.validate_session_access(session_id, user_token):
        return JSONResponse({
            "success": False,
            "message": "无权访问此会话"
        }, status_code=403)
    
    session = manager.get_session(session_id)
    if session:
        manager.complete_session(session_id)
        return JSONResponse({
            "success": True,
            "message": "会话已终止"
        })
    return JSONResponse({
        "success": False,
        "message": "会话不存在"
    }, status_code=404)


# === 全局异常处理器 ===

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常捕获，返回友好的错误信息"""
    # 记录详细错误日志
    logger.error(
        f"Unhandled exception: {str(exc)}",
        path=request.url.path,
        method=request.method,
        client_ip=request.client.host if request.client else "unknown",
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "服务器内部错误，请稍后重试",
            "error_id": str(time.time())
        }
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """404 错误处理"""
    logger.warning(
        "Resource not found",
        path=request.url.path,
        method=request.method
    )
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": "请求的资源不存在"
        }
    )


@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc):
    """405 错误处理"""
    logger.warning(
        "Method not allowed",
        path=request.url.path,
        method=request.method
    )
    return JSONResponse(
        status_code=405,
        content={
            "success": False,
            "message": "请求方法不允许"
        }
    )


@app.exception_handler(429)
async def rate_limit_handler(request: Request, exc):
    """429 速率限制错误"""
    logger.warning(
        "Rate limit exceeded",
        path=request.url.path,
        client_ip=request.client.host if request.client else "unknown"
    )
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "message": "请求过于频繁，请稍后再试"
        }
    )


# === 启动/关闭事件 ===

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    logger.info(
        "MedPaperWriter starting up",
        host=settings.HOST,
        port=settings.PORT,
        debug=settings.DEBUG,
        model=settings.LLM_MODEL
    )

    # 验证配置
    missing = settings.validate()
    if missing:
        logger.warning(
            "Missing configuration items",
            missing=missing
        )


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    logger.info("MedPaperWriter shutting down")


if __name__ == "__main__":
    import uvicorn
    logger.info(
        f"Starting server at http://{settings.HOST}:{settings.PORT}"
    )
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        log_level="info"
    )
